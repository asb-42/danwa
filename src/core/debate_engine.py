import uuid
import json
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from .llm_router import LLMRouter
from .trace_logger import TraceLogger
from src.tools.web_search import WebSearchTool, extract_json_list
from .memory import DebateMemory
from .privacy import PrivacyGuard
from .prompt_manager import PromptManager

PROMPT_DIR = Path("config/prompts")
CLAIM_EXTRACTION_PROMPT = """
Extract up to 3 concrete, verifiable claims or facts from the following text.
Respond ONLY with a JSON list of strings. Example: ["Claim 1", "Claim 2"]
"""


@dataclass
class DebateState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    context: str = ""
    rounds: list[Dict] = field(default_factory=list)
    final_consensus: float = 0.0
    output: str = ""
    validation_report: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    precedents_retrieved: List[Dict] = field(default_factory=list)
    used_variant: str = ""
    used_agent_profile: str = ""


class DebateEngine:
    def __init__(
        self,
        profile_name: str | None = None,
        max_rounds: int = 3,
        threshold: float = 0.75,
        enable_fact_check: bool = True,
        enable_memory: bool = False,
        rag_context: Optional[str] = None,
        agent_profile_name: Optional[str] = None,
    ):
        # Load configuration
        with open("config/settings.yaml") as f:
            settings = yaml.safe_load(f)

        self.router = LLMRouter(profile_name)
        self.search_tool = (
            WebSearchTool(
                engine=settings["search"]["engine"],
                searx_url=settings["search"]["url"],
                max_results=settings["search"]["max_results"],
            )
            if enable_fact_check
            else None
        )

        self.max_rounds = max_rounds
        self.threshold = threshold
        self.logger = None
        self.memory = DebateMemory() if enable_memory else None
        self.privacy = PrivacyGuard(
            strict_mode=settings["privacy"]["strict_mode"],
            retention_days=settings["privacy"]["retention_days"],
        )
        self.prompt_mgr = PromptManager()
        self.state = DebateState()
        self.rag_context = rag_context

        # Load agent profile
        self._agent_profile = None
        self._agent_profile_name = ""
        if agent_profile_name:
            self._load_agent_profile(agent_profile_name, settings)

    def _load_agent_profile(self, profile_name: str, settings: Dict):
        """Load an agent profile and configure per-role LLM assignments."""
        profiles = settings.get("agent_profiles", {}).get("profiles", {})
        if profile_name not in profiles:
            raise ValueError(f"Agent profile '{profile_name}' not found in settings.yaml")
        self._agent_profile = profiles[profile_name]
        self._agent_profile_name = profile_name
        self.state.used_agent_profile = profile_name

        # Configure per-role LLM profiles
        for agent in self._agent_profile.get("agents", []):
            role = agent["role"]
            llm_profile = agent["llm_profile"]
            self.router.set_role_profile(role, llm_profile)

    def _get_agent_roles(self) -> List[Dict]:
        """Get the list of agent roles from the active profile."""
        if self._agent_profile:
            return self._agent_profile.get("agents", [])
        # Fallback to classic 4-agent setup
        return [
            {"role": "strategist", "temperature": 0.4},
            {"role": "critic", "temperature": 0.8},
            {"role": "optimizer", "temperature": 0.3},
            {"role": "moderator", "temperature": 0.2},
        ]

    def _get_last_draft(self, current_draft: str, role: str, round_data: Dict) -> str:
        """Build context from previous agents in the same round."""
        if not round_data:
            return current_draft
        parts = []
        for agent in round_data.get("agents", []):
            if agent["role"] == role:
                break
            parts.append(f"### {agent['role'].capitalize()}\n{agent['content']}")
        if parts:
            return "\n\n".join(parts) + f"\n\n## Current Draft\n{current_draft}"
        return current_draft

    def _load_prompt(self, role: str) -> str:
        return (PROMPT_DIR / f"{role}.md").read_text(encoding="utf-8")

    async def _extract_claims(self, draft: str) -> List[str]:
        resp = await self.router.call(CLAIM_EXTRACTION_PROMPT, draft, temp_override=0.1)
        return extract_json_list(resp["content"])

    async def _run_search_validation(self, draft: str) -> List[Dict]:
        claims = await self._extract_claims(draft)
        validation = []
        for claim in claims:
            results = await self.search_tool.search(claim)
            validation.append({"claim": claim, "evidence": results})
        return validation

    async def run(
        self,
        context: str,
        progress_callback=None,
        variant_override: Optional[str] = None,
    ) -> DebateState:
        # Privacy enforcement: Block external calls in strict mode
        if self.privacy.strict_mode:
            if progress_callback:
                await progress_callback(
                    "privacy",
                    "🔒 STRICT MODE: External validation & cloud LLMs disabled.",
                )
            self.search_tool = None

        self.state.context = context

        if self.rag_context and self.rag_context.strip():
            self.state.context += f"\n\n## RAG Context\n{self.rag_context}"

        # Prompt variant assignment
        assigned_variant = variant_override or self.prompt_mgr.assign_variant(
            self.state.session_id
        )
        self.state.used_variant = assigned_variant
        if progress_callback:
            await progress_callback("prompt", f"Variant: {assigned_variant}")

        # Precedence injection: Search for similar past debates and inject insights
        if self.memory:
            if progress_callback:
                await progress_callback("memory", "Searching precedents...")
            precedents = self.memory.search_precedents(context, top_k=2)
            self.state.precedents_retrieved = precedents
            if precedents and self.state.context:
                try:
                    precedent_insights = (
                        "\n\nRelevant precedents from previous debates:\n"
                    )
                    for i, prec in enumerate(precedents, 1):
                        precedent_insights += f"{i}. Consensus: {prec['metadata']['consensus']:.2f} | Relevance: {prec['relevance_score']:.2f}\n"
                        precedent_insights += f"   {prec['document'][:200]}...\n"
                    self.state.context += precedent_insights
                except Exception as e:
                    # Continue without precedence injection if memory search fails
                    pass

        self.logger = TraceLogger(self.state.session_id)
        if progress_callback:
            await progress_callback("start", "Initializing debate...")

        current_draft = context
        consensus = 0.0
        agent_roles = self._get_agent_roles()

        for r in range(1, self.max_rounds + 1):
            if progress_callback:
                await progress_callback("round", f"Round {r}/{self.max_rounds}")

            round_data = {"round": r, "agents": []}

            # Run each agent in sequence
            for agent_config in agent_roles:
                role = agent_config["role"]
                temp = agent_config.get("temperature", 0.5)

                if progress_callback:
                    await progress_callback("agent", role.capitalize())

                prompt_data = self.prompt_mgr.get(role, assigned_variant)

                # Build user prompt based on role
                if role == "strategist" or (role == "proponent" and r == 1):
                    user_msg = f"Facts:\n{self.state.context}\n\nCurrent state:\n{current_draft}"
                elif role == "critic" or role == "opponent":
                    prev_content = round_data["agents"][-1]["content"] if round_data["agents"] else current_draft
                    user_msg = f"Draft to review:\n{prev_content}"
                elif role == "optimizer":
                    parts = [f"Strategy:\n{round_data['agents'][0]['content']}"]
                    if len(round_data["agents"]) > 1:
                        parts.append(f"Criticism:\n{round_data['agents'][1]['content']}")
                    user_msg = "\n".join(parts)
                elif role == "moderator":
                    search_context = ""
                    if self.search_tool:
                        if progress_callback:
                            await progress_callback("tool", "Web validation")
                        validation = await self._run_search_validation(current_draft)
                        self.state.validation_report = validation
                        self.logger.log(
                            f"R{r}",
                            "search_validation",
                            CLAIM_EXTRACTION_PROMPT,
                            json.dumps(validation),
                            {"claims_checked": len(validation)},
                            prompt_version="unversioned",
                            prompt_hash="hardcoded",
                            prompt_variant=assigned_variant,
                        )
                        if validation:
                            search_context = f"\n\nExternal validation results:\n{json.dumps(validation, ensure_ascii=False, indent=2)}"
                    user_msg = f"Final version:{search_context}\n\nRate consensus from 0.0 to 1.0. Respond ONLY with a number."
                else:
                    # Generic fallback for custom roles
                    prev = round_data["agents"][-1]["content"] if round_data["agents"] else current_draft
                    user_msg = f"Context:\n{self.state.context}\n\nPrevious:\n{prev}"

                resp = await self.router.call(
                    prompt_data["content"],
                    user_msg,
                    temp_override=temp,
                    role=role,
                )
                self.logger.log(
                    f"R{r}",
                    role,
                    prompt_data["content"],
                    resp["content"],
                    {"tokens": resp["tokens_used"]},
                    prompt_version=prompt_data["version"],
                    prompt_hash=prompt_data["hash"],
                    prompt_variant=assigned_variant,
                )
                round_data["agents"].append({
                    "role": role,
                    "content": resp["content"],
                })

                # The last non-moderator agent produces the draft
                if role == "optimizer" or (role not in ("moderator", "optimizer") and agent_config == agent_roles[-2] if len(agent_roles) > 1 else agent_config == agent_roles[-1]):
                    current_draft = resp["content"]

            # Handle moderator consensus
            moderator_agents = [a for a in round_data["agents"] if a["role"] == "moderator"]
            if len(agent_roles) == 1:
                # Single-agent (chatbot) mode — always consensus after first round
                consensus = 1.0
            elif moderator_agents:
                try:
                    consensus = float(moderator_agents[-1]["content"].strip().split()[0])
                except Exception:
                    consensus = 0.5
            else:
                # No moderator — use a simple heuristic
                consensus = min(0.5 + r * 0.15, 1.0)

            self.state.rounds.append({
                "round": r,
                "consensus": consensus,
                "draft_preview": current_draft[:150],
                "agents": [a["role"] for a in round_data["agents"]],
            })

            if consensus >= self.threshold:
                break

        self.state.final_consensus = consensus
        self.state.output = current_draft

        # Store debate in memory for future reference
        if self.memory:
            try:
                self.memory.store_debate(self.state)
            except Exception as e:
                # Continue even if memory storage fails
                pass

        # Apply privacy redaction to traces if enabled
        if self.privacy.redact_traces and self.logger:
            for log_entry in self.logger.get_session_log():
                log_entry["response_full"] = self.privacy.redact_text(
                    log_entry["response_full"]
                )

        return self.state
