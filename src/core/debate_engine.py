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
Extrahiere aus folgendem Text maximal 3 konkrete, überprüfbare Behauptungen oder Fakten.
Antworte NUR mit einer JSON-Liste von Strings. Beispiel: ["Behauptung 1", "Behauptung 2"]
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


class DebateEngine:
    ROLE_TEMPS = {"strategist": 0.4, "critic": 0.8, "optimizer": 0.3, "moderator": 0.2}

    def __init__(
        self,
        profile_name: str = "local_lm_studio",
        max_rounds: int = 3,
        threshold: float = 0.75,
        enable_fact_check: bool = True,
        enable_memory: bool = False,
        rag_context: Optional[str] = None,
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
                    "🔒 STRICT MODE: Externe Validierung & Cloud-LLMs deaktiviert.",
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
            await progress_callback("prompt", f"Variante: {assigned_variant}")

        # Precedence injection: Search for similar past debates and inject insights
        if self.memory:
            if progress_callback:
                await progress_callback("memory", "Suche Präzedenzfälle...")
            precedents = self.memory.search_precedents(context, top_k=2)
            self.state.precedents_retrieved = precedents
            if precedents and self.state.context:
                try:
                    precedent_insights = (
                        "\n\nRelevante Präzedenzfälle aus früheren Debatten:\n"
                    )
                    for i, prec in enumerate(precedents, 1):
                        precedent_insights += f"{i}. Konsens: {prec['metadata']['consensus']:.2f} | Relevanz: {prec['relevance_score']:.2f}\n"
                        precedent_insights += f"   {prec['document'][:200]}...\n"
                    self.state.context += precedent_insights
                except Exception as e:
                    # Continue without precedence injection if memory search fails
                    pass

        self.logger = TraceLogger(self.state.session_id)
        if progress_callback:
            await progress_callback("start", "Initialisiere Debatte...")

        current_draft = context
        consensus = 0.0

        for r in range(1, self.max_rounds + 1):
            if progress_callback:
                await progress_callback("round", f"Runde {r}/{self.max_rounds}")

            # 1. Strategie
            if progress_callback:
                await progress_callback("agent", "Strategist")
            prompt_data = self.prompt_mgr.get("strategist", assigned_variant)
            strat = await self.router.call(
                prompt_data["content"],
                f"Sachverhalt:\n{self.state.context}\nAktueller Stand:\n{current_draft}",
                self.ROLE_TEMPS["strategist"],
            )
            self.logger.log(
                f"R{r}",
                "strategist",
                prompt_data["content"],
                strat["content"],
                {"tokens": strat["tokens_used"]},
                prompt_version=prompt_data["version"],
                prompt_hash=prompt_data["hash"],
                prompt_variant=assigned_variant,
            )

            # 2. Kritik
            if progress_callback:
                await progress_callback("agent", "Critic")
            prompt_data = self.prompt_mgr.get("critic", assigned_variant)
            crit = await self.router.call(
                prompt_data["content"],
                f"Strategie-Entwurf:\n{strat['content']}",
                self.ROLE_TEMPS["critic"],
            )
            self.logger.log(
                f"R{r}",
                "critic",
                prompt_data["content"],
                crit["content"],
                {"tokens": crit["tokens_used"]},
                prompt_version=prompt_data["version"],
                prompt_hash=prompt_data["hash"],
                prompt_variant=assigned_variant,
            )

            # 3. Optimierung
            if progress_callback:
                await progress_callback("agent", "Optimizer")
            prompt_data = self.prompt_mgr.get("optimizer", assigned_variant)
            opt = await self.router.call(
                prompt_data["content"],
                f"Strategie:\n{strat['content']}\nKritik:\n{crit['content']}",
                self.ROLE_TEMPS["optimizer"],
            )
            self.logger.log(
                f"R{r}",
                "optimizer",
                prompt_data["content"],
                opt["content"],
                {"tokens": opt["tokens_used"]},
                prompt_version=prompt_data["version"],
                prompt_hash=prompt_data["hash"],
                prompt_variant=assigned_variant,
            )
            current_draft = opt["content"]

            # 4. Fact-Check (optional)
            validation = []
            if self.search_tool:
                if progress_callback:
                    await progress_callback("tool", "Web-Validierung")
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

            # 5. Moderator / Konsens
            if progress_callback:
                await progress_callback("agent", "Moderator")
            search_context = (
                f"\n\nExterne Validierungsergebnisse:\n{json.dumps(validation, ensure_ascii=False, indent=2)}"
                if validation
                else ""
            )
            prompt_data = self.prompt_mgr.get("moderator", assigned_variant)
            mod = await self.router.call(
                prompt_data["content"],
                f"Finale Fassung:{search_context}\n\nBewerte Konsens auf 0.0 bis 1.0. Antworte NUR mit einer Zahl.",
                self.ROLE_TEMPS["moderator"],
            )

            try:
                consensus = float(mod["content"].strip().split()[0])
            except Exception:
                consensus = 0.5

            self.state.rounds.append(
                {
                    "round": r,
                    "consensus": consensus,
                    "draft_preview": current_draft[:150],
                }
            )
            self.logger.log(
                f"R{r}",
                "moderator",
                prompt_data["content"],
                mod["content"],
                {"consensus": consensus},
                prompt_version=prompt_data["version"],
                prompt_hash=prompt_data["hash"],
                prompt_variant=assigned_variant,
            )

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
