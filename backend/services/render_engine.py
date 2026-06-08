"""RenderEngineService — orchestrates render job lifecycle.

Validates submissions, dispatches to output plugins, and tracks
job status through ``queued → running → completed | failed``.
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

_DEFAULT_OUTPUT_DIR = Path("output")


# Keep references to background tasks to prevent GC before completion.
_background_tasks: set[asyncio.Task] = set()


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
        """Initialise RenderEngineService."""
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

        # 2. Load artifact (with fallback: build from debate store)
        artifact = self.artifact_store.get(session_id)
        if artifact is None:
            artifact = self._build_artifact_from_debate_store(session_id)
            if artifact is None:
                raise ValueError(f"No DebateArtifact found for session {session_id!r}. Ensure the workflow has completed and the artifact was saved.")

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

        # 6. Schedule async execution (store ref to prevent GC)
        task = asyncio.create_task(self.execute_job(job.id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

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
            # Reload artifact (with fallback)
            artifact = self.artifact_store.get(job.session_id)
            if artifact is None:
                artifact = self._build_artifact_from_debate_store(job.session_id)
            if artifact is None:
                raise ValueError(f"DebateArtifact for session {job.session_id!r} disappeared")

            # Get plugin and validate config
            plugin_cls = self.registry.get_plugin(job.plugin_key)
            config = plugin_cls.validate_config(job.config)

            # Instantiate plugin (stateless — fresh instance per call)
            plugin = plugin_cls()

            # Build progress callback that writes to the job store
            async def _update_progress(current: int, total: int) -> None:
                """Update progress the instance."""
                self.job_store.update_job(
                    job_id,
                    progress_current=current,
                    progress_total=total,
                )

            # Render
            output_dir = self.output_dir
            output_paths = await plugin.render(
                artifact=artifact,
                config=config,
                job_id=job_id,
                output_dir=output_dir,
                progress_callback=_update_progress,
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

    # ------------------------------------------------------------------
    # Fallback: build artifact from debate store
    # ------------------------------------------------------------------

    def _build_artifact_from_debate_store(self, session_id: str):
        """Fallback: build a DebateArtifact from the debate store for legacy sessions.

        Searches all projects for a debate with the given session_id and builds
        an artifact from its rounds/result data.  Returns None if not found.
        """
        from backend.api.deps import get_case_dir, get_project_store
        from backend.persistence.debate_store import DebateStore

        # Try direct key lookup first (legacy debates keyed by session_id)
        try:
            for project in get_project_store().list_all():
                project_dir = get_case_dir(project.id)
                store = DebateStore(data_dir=project_dir / "debates")
                debate = store.get(session_id)
                if debate:
                    artifact = _debate_to_artifact(debate)
                    self.artifact_store.save(artifact)
                    return artifact
        except Exception as exc:
            logger.warning("Failed to build artifact from debate store for %s: %s", session_id, exc)

        # Try by session_id field (MVP debates: session_id=wf-xxx, key=debate_id=mvp-xxx)
        try:
            for project in get_project_store().list_all():
                project_dir = get_case_dir(project.id)
                store = DebateStore(data_dir=project_dir / "debates")
                for d in store.list_all(limit=500):
                    if d.get("session_id") == session_id:
                        artifact = _debate_to_artifact(d)
                        self.artifact_store.save(artifact)
                        return artifact
        except Exception as exc:
            logger.warning("Failed to search debates by session_id %s: %s", session_id, exc)

        # Second fallback: try global DebateStore (data/debates)
        try:
            global_store = DebateStore()
            debate = global_store.get(session_id)
            if debate:
                artifact = _debate_to_artifact(debate)
                self.artifact_store.save(artifact)
                return artifact
            # Also search by session_id field in global store
            for d in global_store.list_all(limit=500):
                if d.get("session_id") == session_id:
                    artifact = _debate_to_artifact(d)
                    self.artifact_store.save(artifact)
                    return artifact
        except Exception as exc:
            logger.warning("Failed to build artifact from global debate store for %s: %s", session_id, exc)

        # Third fallback: resolve A2A task_id → debate_id
        try:
            from backend.a2a.task_manager import TaskManager

            tm = TaskManager()
            task = tm.get_task(session_id)
            if task and task.get("debate_id"):
                debate_id = task["debate_id"]
                return self._build_artifact_from_debate_store(debate_id)
        except Exception as exc:
            logger.debug("A2A task resolution for %s failed: %s", session_id, exc)

        return None


def _normalize_or_pass(content: str, role: str) -> str:
    """Normalize structured JSON output (critic/builder/pragmatist) to Markdown."""
    from backend.workflow.workflow_runner import normalize_transcript_content

    return normalize_transcript_content(content, role)


def _build_turns_from_node_outputs(
    node_outputs: list[dict],
    node_configs: dict | None = None,
    llm_assignments: dict | None = None,
) -> list:
    """Convert workflow ``node_outputs`` (from state snapshots) to ``Turn`` objects.

    MVP debates store per-agent content in ``node_outputs`` rather than the
    legacy ``rounds[n].agent_outputs`` format used by the original debate engine.

    Args:
        node_outputs: List of WorkflowNodeOutput dicts (snake_case keys).
        node_configs: Optional node_id → config dict (from state snapshot).
            Used to resolve LLM profile info for agent display names.
        llm_assignments: Optional role → llm_profile_id mapping (from debate record).
            Fallback when node_configs is not available.
    """
    from backend.models.artifact import Turn

    node_configs = node_configs or {}
    llm_assignments = llm_assignments or {}

    # Build node_id → config lookup
    config_by_node: dict[str, dict] = {}
    for nid, cfg in node_configs.items():
        if isinstance(cfg, str):
            # Serialized as string in snapshot — try to eval
            try:
                import ast

                cfg = ast.literal_eval(cfg)
            except (ValueError, SyntaxError):
                cfg = {}
        config_by_node[nid] = cfg if isinstance(cfg, dict) else {}

    _system_roles = {"complete", "input", "initialize"}
    turns: list[Turn] = []
    for no in node_outputs:
        role = no.get("role") or no.get("node_type", "agent")
        if role in _system_roles:
            continue
        rnd = no.get("round", 0)
        node_id = no.get("node_id", f"{role}_round{rnd}")

        # Resolve LLM profile info for display name
        config = config_by_node.get(node_id, {})
        llm_model = config.get("llm_model", "")
        llm_profile_id = config.get("llm_profile_id", "")
        llm_profile_name = config.get("llm_profile_name", "")
        role_type_name = config.get("role_type_name", role.title())

        # Fallback: use llm_assignments from debate record
        if not llm_profile_id:
            llm_profile_id = llm_assignments.get(role, "")

        # Build descriptive agent name: "Critic (owl-alpha)"
        agent_name = role_type_name or role.title()
        if llm_model:
            agent_name = f"{agent_name} ({llm_model})"
        elif llm_profile_name:
            agent_name = f"{agent_name} ({llm_profile_name})"
        elif llm_profile_id:
            agent_name = f"{agent_name} ({llm_profile_id})"

        turns.append(
            Turn(
                round=rnd,
                node_id=node_id,
                agent_name=agent_name,
                role_type=role,
                llm_profile_id=llm_profile_id,
                llm_profile_name=llm_profile_name,
                content=_normalize_or_pass(no.get("content", ""), role),
                latency_ms=no.get("duration_ms", 0),
                token_usage={"total": no.get("tokens_used", 0)},
            )
        )
    return turns


def _debate_to_artifact(debate: dict):
    """Convert a debate store dict into a DebateArtifact."""
    from backend.models.artifact import DebateArtifact, Turn

    result = debate.get("result", {})
    rounds = debate.get("rounds", [])
    if not rounds and result:
        rounds = result.get("rounds", [])
    req = debate.get("request", {})

    turns: list[Turn] = []

    # MVP debates store content in workflow state snapshot node_outputs
    if debate.get("is_mvp"):
        session_id = debate.get("session_id")
        if session_id:
            try:
                from backend.workflow.state_snapshot import StateSnapshotStore

                snap_store = StateSnapshotStore()
                snapshot = snap_store.get_latest(session_id)
                if snapshot:
                    state = snapshot.get("state", {})
                    node_outputs = state.get("node_outputs", [])
                    node_configs = state.get("node_configs", {})
                    llm_assignments = debate.get("llm_assignments", {})
                    turns = _build_turns_from_node_outputs(
                        node_outputs,
                        node_configs=node_configs,
                        llm_assignments=llm_assignments,
                    )
            except Exception as exc:
                logger.warning("Failed to load snapshot for MVP debate %s: %s", session_id, exc)
    else:
        # Legacy debates: build turns from rounds[n].agent_outputs
        for rd in rounds:
            for ao in rd.get("agent_outputs", []):
                role = ao.get("role", "agent")
                turns.append(
                    Turn(
                        round=rd.get("round", 0),
                        node_id=f"{role}_round{rd.get('round', 0)}",
                        agent_name=role,
                        role_type=role,
                        content=_normalize_or_pass(ao.get("content", ""), role),
                        token_usage={"total": ao.get("tokens_used", 0)},
                    )
                )

    case_text = ""
    if isinstance(req.get("case"), dict):
        case_text = req["case"].get("text", "")
    elif req.get("case"):
        case_text = str(req["case"])

    # Determine consensus score: MVP uses consensus field, legacy uses final_consensus
    consensus_score = result.get("final_consensus")
    if consensus_score is None:
        consensus_score = result.get("consensus", 0.0)

    metadata_title = debate.get("title", "")
    metadata_language = req.get("language", "de")

    return DebateArtifact(
        session_id=debate.get("debate_id", ""),
        workflow_id=f"debate_{debate.get('debate_id', '')[:8]}",
        workflow_version=1,
        workflow_name="debate",
        title=debate.get("title", ""),
        topic=case_text,
        transcript=turns,
        consensus_result={
            "score": consensus_score,
            "summary": result.get("output", ""),
        },
        metadata={
            "token_usage": {
                "total": sum(t.token_usage.get("total", 0) for t in turns),
            },
            "title": metadata_title,
            "language": metadata_language,
        },
    )
