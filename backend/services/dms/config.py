"""DMS configuration defaults.

Migrated from src/dms/config.py.
"""

import yaml

DEFAULT_DMS_CONFIG = {
    "enabled": True,
    "storage_path": "dms_storage",
    "chunk_size": 512,
    "chunk_overlap": 51,
    "embedding_model": "intfloat/multilingual-e5-small",
    "ocr_enabled": True,
    "ocr_device": "cpu",
    "ocr_lang": "deu+eng",
    "ocr_preferred_engine": "auto",
    "max_file_size_mb": 50,
    "chroma_collection": "document_chunks",
    "memory_dir": "memory",
}


def load_dms_config(config_path: str = "config/settings.yaml") -> dict:
    """Load DMS configuration from YAML file, merged with defaults.

    Falls back to defaults if the config file doesn't exist.
    """
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        dms_config = {**DEFAULT_DMS_CONFIG, **(config.get("dms") or {})}
    except FileNotFoundError:
        dms_config = dict(DEFAULT_DMS_CONFIG)

    chunk_size = dms_config["chunk_size"]
    chunk_overlap = dms_config["chunk_overlap"]
    max_file_size_mb = dms_config["max_file_size_mb"]

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")
    if max_file_size_mb <= 0:
        raise ValueError("max_file_size_mb must be greater than 0")

    return dms_config
