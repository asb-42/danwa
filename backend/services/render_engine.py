"""RenderEngineService — orchestrates render job lifecycle.

Validates, dispatches, and tracks render jobs.  The actual plugin
``render()`` call runs as a background task (FastAPI ``BackgroundTasks``
or ``asyncio.create_task``).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.models.render_job import RenderJob, RenderJobStatus
from backend.services.artifact_store import ArtifactStore
from backend.services.output.registry import PluginRegistry
from backend.services.render_job_store import RenderJobStore

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("data/outputs")


class RenderEngineService:
    """Orchestrates render job lifecycle: validate, dispatch, track.

    Usage::

        engine = RenderEngineService()
        job = await engine.submit_job(session_id, "print", config_dict)
        # job runs asynchronously
        status = engine.job_store.get_job(job.id)
    """

    def __init__(
        self,
        artifact_store: ArtifactStore | None = None,
        job_store: RenderJobStore | None = None,
        registry: PluginRegistry | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.artifact_store = artifact_store or ArtifactStore()
        self.job_store = job_store or RenderJobStore()
        self.registry = registry or PluginRegistry.instance()
        self.output_dir = output_dir or _DEFAULT_OUTPUT_DIR

    async def submit_job(
        self,
        session_id: str,
        plugin_key: str,
        config: dict,
    ) -> RenderJob:
        """Submit a new render job.

        Args:
            session_id: The workflow session whose artifact to render.
            plugin_key: Key of the output plugin to use.
            config: Plugin-specific configuration dictionary.

        Returns:
            The created ``RenderJob`` with status ``queued``.

        Raises:
            KeyError: If the plugin_key is unknown.
            ValueError: If the config is invalid or the artifact is missing.
        """
        # 1. Resolve plugin and validate config
        plugin_cls = self.registry.get_plugin(plugin_key)
        validated_config = plugin_cls.validate_config(config)

        # 2. Load artifact
        artifact = self.artifact_store.get(session_id)
        if artifact is None:
            raise ValueError(
                f"No DebateArtifact found for session {session_id!r}. "
                "Ensure the workflow has completed and the artifact was saved."
            )

        # 3. Compute artifact hash for integrity checking
        artifact_hash = artifact.artifact_hash()

        # 4. Create RenderJob
        job = RenderJob(
            session_id=session_id,
            status=RenderJobStatus.QUEUED,
            plugin_key=plugin_key,
            config=validated_config.model_dump(),
            artifact_snapshot_hash=artifact_hash,
        )
        self.job_store.create_job(job)

        # 5. Create output directory
        job_dir = self.output_dir / job.id
        job_dir.mkdir(parents=True, exist_ok=True)

        # 6. Schedule async execution
        asyncio.create_task(self.execute_job(job.id))

        logger.info(
            "RenderJob %s submitted (plugin=%s, session=%s)",
            job.id,
            plugin_key,
            session_id,
        )
        return job

    async def execute_job(self, job_id: str) -> None:
        """Execute a render job asynchronously.

        Called as a background task after :meth:`submit_job`.  Updates
        the job status through its lifecycle:
        ``queued → running → completed | failed``.

        Args:
            job_id: The render job ID to execute.
        """
        job = self.job_store.get_job(job_id)
        if job is None:
            logger.error("RenderJob %s not found — cannot execute", job_id)
            return

        # Mark as running
        now = datetime.now(UTC)
        self.job_store.update_job(
            job_id,
            status=RenderJobStatus.RUNNING,
            started_at=now,
        )

        try:
            # Reload artifact
            artifact = self.artifact_store.get(job.session_id)
            if artifact is None:
                raise ValueError(
                    f"DebateArtifact for session {job.session_id!r} disappeared"
                )

            # Get plugin and validate config
            plugin_cls = self.registry.get_plugin(job.plugin_key)
            config = plugin_cls.validate_config(job.config)

            # Instantiate plugin (stateless — fresh instance per call)
            plugin = plugin_cls()

            # Render
            output_dir = self.output_dir
            output_paths = await plugin.render(
                artifact=artifact,
                config=config,
                job_id=job_id,
                output_dir=output_dir,
            )

            # Record success
            completed_at = datetime.now(UTC)
            file_paths = [str(p) for p in output_paths]
            self.job_store.update_job(
                job_id,
                status=RenderJobStatus.COMPLETED,
                output_files=file_paths,
                completed_at=completed_at,
            )
            logger.info(
                "RenderJob %s completed — %d file(s) generated",
                job_id,
                len(file_paths),
            )

        except Exception as exc:
            completed_at = datetime.now(UTC)
            self.job_store.update_job(
                job_id,
                status=RenderJobStatus.FAILED,
                error_message=str(exc),
                completed_at=completed_at,
            )
            logger.error(
                "RenderJob %s failed: %s",
                job_id,
                exc,
                exc_info=True,
            )
