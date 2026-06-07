"""InputComposerService — orchestrates input capture via plugins.

This service is the bridge between the API layer and the Input Plugins.
It manages InputJob lifecycle and produces DebateInput artifacts.

The service is NOT responsible for workflow execution — it only
produces the DebateInput artifact.  A separate WorkflowOrchestrator
subscribes to completed input jobs and starts the workflow.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.models.debate_input import DebateInput
from backend.models.input_job import InputJob, InputJobStatus
from backend.services.input.input_job_store import InputJobStore
from backend.services.input.registry import InputPluginRegistry

logger = logging.getLogger(__name__)


class InputComposerService:
    """Orchestrates input capture via registered Input Plugins.

    Usage::

        service = InputComposerService()
        job = await service.submit_input("standard_text", {}, {"topic": "..."})
        # job runs asynchronously or synchronously depending on plugin
    """

    def __init__(
        self,
        job_store: InputJobStore | None = None,
        registry: InputPluginRegistry | None = None,
    ) -> None:
        """Initialise InputComposerService."""
        self.job_store = job_store or InputJobStore()
        self.registry = registry or InputPluginRegistry.instance()

    async def submit_input(
        self,
        plugin_key: str,
        config: dict,
        raw_data: dict[str, Any],
    ) -> InputJob:
        """Submit input for processing by an Input Plugin.

        Args:
            plugin_key: Key of the input plugin to use.
            config: Plugin-specific configuration.
            raw_data: Raw input data (e.g. topic text, audio metadata).

        Returns:
            The created ``InputJob``.

        Raises:
            KeyError: If the plugin_key is unknown.
            ValueError: If the config is invalid.
        """
        # 1. Resolve plugin and validate config
        plugin_cls = self.registry.get_plugin(plugin_key)
        validated_config = plugin_cls.validate_config(config)

        # 2. Create InputJob
        job = InputJob(
            plugin_key=plugin_key,
            config=validated_config.model_dump(),
            raw_input_data=raw_data,
        )

        # 3. Route by plugin type
        if plugin_key == "standard_text":
            # Immediate processing
            topic = raw_data.get("topic", "")
            debate_input = DebateInput(
                source_plugin_key=plugin_key,
                topic=topic,
                source_metadata={"placeholder": config.get("placeholder_text")},
                timestamp=datetime.now(UTC),
            )
            job.status = InputJobStatus.COMPLETED
            job.processed_input = debate_input
            job.completed_at = datetime.now(UTC)
            self.job_store.create_job(job)
            logger.info("Standard text input processed immediately: %s", job.id)

        elif plugin_key == "stt":
            # Processing deferred to streaming endpoint
            job.status = InputJobStatus.PROCESSING
            self.job_store.create_job(job)
            logger.info("STT input job created (waiting for audio): %s", job.id)

        elif plugin_key == "a2a_inbound":
            # Check if approval required
            require_approval = config.get("require_approval", True)
            if require_approval:
                job.status = InputJobStatus.PENDING_APPROVAL
            else:
                job.status = InputJobStatus.PROCESSING
            self.job_store.create_job(job)
            logger.info("A2A inbound job created: %s (approval=%s)", job.id, require_approval)

        else:
            # Generic plugin — try capture
            try:
                plugin = plugin_cls()
                debate_input = await plugin.capture(validated_config)
                # Fill in topic from raw_data
                debate_input = debate_input.model_copy(update={"topic": raw_data.get("topic", debate_input.topic)})
                job.status = InputJobStatus.COMPLETED
                job.processed_input = debate_input
                job.completed_at = datetime.now(UTC)
            except NotImplementedError:
                job.status = InputJobStatus.FAILED
                job.error_message = f"Plugin {plugin_key} is not yet implemented"
            except Exception as exc:
                job.status = InputJobStatus.FAILED
                job.error_message = str(exc)

            self.job_store.create_job(job)

        return job

    async def finalize_input(self, job_id: str, processed_data: DebateInput) -> None:
        """Finalize an input job with processed data.

        Called after STT transcription completes or A2A approval.

        Args:
            job_id: The input job ID.
            processed_data: The finalized ``DebateInput``.
        """
        self.job_store.update_job(
            job_id,
            status=InputJobStatus.COMPLETED,
            processed_input=processed_data,
            completed_at=datetime.now(UTC),
        )
        logger.info("InputJob %s finalized", job_id)

    async def approve_a2a(self, job_id: str) -> InputJob | None:
        """Approve a pending A2A inbound request.

        Args:
            job_id: The input job ID.

        Returns:
            The updated job, or None if not found.
        """
        job = self.job_store.get_job(job_id)
        if job is None:
            return None
        if job.status != InputJobStatus.PENDING_APPROVAL:
            raise ValueError(f"Job {job_id} is not pending approval")

        self.job_store.update_job(job_id, status=InputJobStatus.PROCESSING)
        logger.info("A2A job %s approved", job_id)
        return self.job_store.get_job(job_id)

    async def reject_a2a(self, job_id: str) -> InputJob | None:
        """Reject a pending A2A inbound request.

        Args:
            job_id: The input job ID.

        Returns:
            The updated job, or None if not found.
        """
        job = self.job_store.get_job(job_id)
        if job is None:
            return None
        if job.status != InputJobStatus.PENDING_APPROVAL:
            raise ValueError(f"Job {job_id} is not pending approval")

        self.job_store.update_job(
            job_id,
            status=InputJobStatus.FAILED,
            error_message="Rejected by user",
            completed_at=datetime.now(UTC),
        )
        logger.info("A2A job %s rejected", job_id)
        return self.job_store.get_job(job_id)
