"""UserKeyStore — per-user LLM API key overrides (BYOK).

Stores user-scoped API keys in the auth.db database.

**P3.2 — Envelope encryption (Fernet):**
The plaintext-API-key storage flagged in the 2026-06-12 code review is
fixed. Every key written to the ``api_key`` column is now a Fernet
token (AES-128-CBC + HMAC-SHA256). The Fernet key is resolved at
construction time with the following priority:

1. ``crypto_key`` constructor argument (used by tests + explicit DI).
2. ``DANWA_USER_KEYS_ENCRYPTION_KEY`` environment variable — must be a
   url-safe base64-encoded 32-byte Fernet key. This is the recommended
   production knob.
3. ``DANWA_JWT_SECRET_KEY`` derived via HKDF-SHA256 (so a deployment
   that already configured a JWT secret needs no extra setting).
4. **Ephemeral dev key** generated at process start and persisted to
   ``<data_dir>/.user_keys_key`` for the lifetime of the process
   (per-process stable, lost on restart). This branch emits a loud
   ``WARNING`` at first use and is intended for unit tests + dev
   sandboxes only.

A ``key_id`` column is written next to each ciphertext so a future key
rotation can decrypt with the right historical key. ``get_key`` returns
``None`` (and logs a warning) if decryption fails — i.e. the ciphertext
was produced by a key that is no longer loaded.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")

_DEV_KEY_FILENAME = ".user_keys_key"
_DEV_KEY_ID_PREFIX = "dev"

# Cache of resolved (db_path -> (fernet_key, key_id)) for the
# dev fallback. We key on the resolved db_path so that multiple
# UserKeyStore instances pointing at *different* database files
# (e.g. one per test in tmp_path) do not collide and try to
# re-use each other's key files.
_DEV_KEY_CACHE: dict[str, tuple[bytes, str]] = {}


def _hkdf(secret: bytes, length: int, info: str, salt: bytes | None = None) -> bytes:
    """Small HKDF-SHA256 implementation (RFC 5869) — no extra dep.

    Used to derive a 32-byte Fernet key from ``DANWA_JWT_SECRET_KEY``.
    """
    if salt is None:
        salt = b"\x00" * 32
    prk = hmac.new(salt, secret, hashlib.sha256).digest()

    def expand(counter: int) -> bytes:
        return hmac.new(prk, info.encode("utf-8") + counter.to_bytes(1, "big"), hashlib.sha256).digest()

    out = b""
    counter = 1
    while len(out) < length:
        out += expand(counter)
        counter += 1
    return out[:length]


def _derive_fernet_key_from_jwt() -> bytes:
    """Derive a 32-byte Fernet key from ``DANWA_JWT_SECRET_KEY`` via HKDF."""
    from backend.core.config import settings  # local import to avoid cycles

    secret = settings.jwt_secret_key.encode("utf-8")
    derived = _hkdf(secret, 32, info="danwa.user_keys.fernet")
    return base64.urlsafe_b64encode(derived)


def _load_or_create_dev_key(db_path: Path) -> tuple[bytes, str]:
    """Return ``(fernet_key_bytes, key_id)`` for the dev fallback.

    The key is persisted next to the SQLite database so that a single
    long-running process can survive re-construction of the
    ``UserKeyStore`` (e.g. FastAPI reloads) without losing access to
    previously-written ciphertexts. The key file is created with mode
    0o600 and ignored by ``.gitignore``.
    """
    cache_key = str(db_path.resolve())
    cached = _DEV_KEY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    key_file = db_path.parent / _DEV_KEY_FILENAME
    if key_file.exists():
        try:
            fernet_key = key_file.read_bytes()
            key_id = hashlib.sha256(fernet_key).hexdigest()[:12]
            full_id = f"{_DEV_KEY_ID_PREFIX}:{key_id}"
            _DEV_KEY_CACHE[cache_key] = (fernet_key, full_id)
            logger.warning(
                "UserKeyStore: using DEV-FALLBACK Fernet key from %s. "
                "Set DANWA_USER_KEYS_ENCRYPTION_KEY (or "
                "DANWA_JWT_SECRET_KEY) for production deployments.",
                key_file,
            )
            return fernet_key, full_id
        except OSError as exc:
            logger.error("UserKeyStore: could not read dev key file %s: %s", key_file, exc)

    # First call: generate a new random key and persist it.
    fernet_key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(fernet_key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    except OSError as exc:
        logger.warning("UserKeyStore: could not persist dev key file %s: %s", key_file, exc)
    key_id = hashlib.sha256(fernet_key).hexdigest()[:12]
    full_id = f"{_DEV_KEY_ID_PREFIX}:{key_id}"
    _DEV_KEY_CACHE[cache_key] = (fernet_key, full_id)
    logger.warning(
        "UserKeyStore: generated NEW DEV-FALLBACK Fernet key (id=%s). Stored at %s. Set DANWA_USER_KEYS_ENCRYPTION_KEY for production.",
        full_id,
        key_file,
    )
    return fernet_key, full_id


def _load_dev_key_file(db_path: Path) -> bytes:
    key_file = db_path.parent / _DEV_KEY_FILENAME
    return key_file.read_bytes()


def resolve_fernet_key(db_path: Path, crypto_key: bytes | None = None) -> tuple[bytes, str]:
    """Resolve the active Fernet key + key_id for a given DB location.

    Precedence (highest first):
    1. ``crypto_key`` arg
    2. ``DANWA_USER_KEYS_ENCRYPTION_KEY`` env var
    3. ``DANWA_JWT_SECRET_KEY`` derived via HKDF
    4. Dev fallback (persisted file or freshly generated)
    """
    if crypto_key is not None:
        if len(crypto_key) < 16:
            raise ValueError("crypto_key must be at least 16 bytes (Fernet expects 32 base64-encoded bytes)")
        key_id = "explicit:" + hashlib.sha256(crypto_key).hexdigest()[:12]
        return crypto_key, key_id

    env_key = os.environ.get("DANWA_USER_KEYS_ENCRYPTION_KEY", "").strip()
    if env_key:
        try:
            decoded = base64.urlsafe_b64decode(env_key.encode("ascii"))
            if len(decoded) != 32:
                raise ValueError(f"expected 32 bytes, got {len(decoded)}")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"DANWA_USER_KEYS_ENCRYPTION_KEY is not a valid Fernet key: {exc}") from exc
        key_id = "env:" + hashlib.sha256(env_key.encode("ascii")).hexdigest()[:12]
        return env_key.encode("ascii"), key_id

    from backend.core.config import settings  # local import to avoid cycles

    if settings.jwt_secret_key:
        try:
            derived = _derive_fernet_key_from_jwt()
            key_id = "jwt:" + hashlib.sha256(derived).hexdigest()[:12]
            return derived, key_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("UserKeyStore: could not derive Fernet key from JWT secret: %s", exc)

    return _load_or_create_dev_key(db_path)


class UserKeyStore:
    """CRUD operations for user-scoped LLM API keys (envelope-encrypted)."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        crypto_key: bytes | None = None,
    ):
        """Initialise UserKeyStore.

        Args:
            db_path: Path to the SQLite database. Defaults to ``data/auth.db``.
            crypto_key: Optional explicit Fernet key (32 raw bytes or
                url-safe base64). When ``None``, the key is resolved via
                ``resolve_fernet_key()`` (env / JWT-derived / dev fallback).
        """
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        fernet_key, key_id = resolve_fernet_key(self.db_path, crypto_key)
        self._fernet_key = fernet_key
        self._key_id = key_id
        # Imported lazily so that the module can be imported even if
        # ``cryptography`` is somehow missing — the explicit failure
        # surface is then at the call site rather than at import.
        from cryptography.fernet import Fernet, InvalidToken

        self._InvalidToken = InvalidToken
        self._fernet = Fernet(fernet_key)

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    # -- crypto helpers ----------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")

    def _decrypt(self, ciphertext: str) -> str | None:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except self._InvalidToken:
            logger.warning(
                "UserKeyStore: failed to decrypt API key (key_id=%s) — the row may have been written with a different key",
                self._key_id,
            )
            return None

    # -- schema ------------------------------------------------------------

    def _init_db(self) -> None:
        """Init db the instance."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_llm_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                api_key TEXT NOT NULL,
                key_id TEXT NOT NULL DEFAULT '',
                label TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, profile_id)
            )
        """)
        # Backfill columns for existing databases (P3.2 migration).
        try:
            self.conn.execute("ALTER TABLE user_llm_keys ADD COLUMN key_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_user_keys_user ON user_llm_keys(user_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_user_keys_profile ON user_llm_keys(profile_id)")
        self.conn.commit()

    # -- CRUD --------------------------------------------------------------

    def set_key(self, user_id: str, profile_id: str, api_key: str, label: str = "") -> None:
        """Store or update an API key for a user+profile combination."""
        if not api_key:
            raise ValueError("api_key must be a non-empty string")

        ciphertext = self._encrypt(api_key)
        now = datetime.now(UTC).isoformat()
        key_id = f"{user_id}:{profile_id}"
        self.conn.execute(
            """INSERT INTO user_llm_keys (id, user_id, profile_id, api_key, key_id, label, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, profile_id) DO UPDATE SET
                api_key = excluded.api_key,
                key_id = excluded.key_id,
                label = excluded.label,
                updated_at = excluded.updated_at""",
            (key_id, user_id, profile_id, ciphertext, self._key_id, label, now, now),
        )
        self.conn.commit()
        logger.info("Stored encrypted BYOK key for user %s, profile %s", user_id, profile_id)

    def get_key(self, user_id: str, profile_id: str) -> str | None:
        """Retrieve an API key for a user+profile. Returns None if not set or decrypt fails."""
        cursor = self.conn.execute(
            "SELECT api_key FROM user_llm_keys WHERE user_id = ? AND profile_id = ?",
            (user_id, profile_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._decrypt(row["api_key"])

    def list_keys(self, user_id: str) -> list[dict]:
        """List all API keys for a user (keys are masked in the response)."""
        cursor = self.conn.execute(
            "SELECT profile_id, label, created_at, updated_at FROM user_llm_keys WHERE user_id = ?",
            (user_id,),
        )
        return [
            {
                "profile_id": row["profile_id"],
                "label": row["label"],
                "has_key": True,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in cursor.fetchall()
        ]

    def delete_key(self, user_id: str, profile_id: str) -> bool:
        """Delete an API key for a user+profile. Returns True if deleted."""
        self.conn.execute(
            "DELETE FROM user_llm_keys WHERE user_id = ? AND profile_id = ?",
            (user_id, profile_id),
        )
        self.conn.commit()
        return True

    def delete_all_keys(self, user_id: str) -> int:
        """Delete all API keys for a user. Returns count of deleted keys."""
        cursor = self.conn.execute("DELETE FROM user_llm_keys WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount
