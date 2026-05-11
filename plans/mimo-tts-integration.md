# MiMo-V2.5-TTS Integration for Audio Export

## Problem

The existing TTS export uses only **edge-tts** (Microsoft's free TTS). While functional, it lacks:
- Style control (tone, pace, emotion)
- LLM-driven natural language voice direction
- Per-agent persona voice assignment from the blueprint system

**MiMo-V2.5-TTS** (Xiaomi) offers LLM-driven TTS via an OpenAI-compatible API with natural language style control, making it ideal for debate podcast generation where each agent persona should have a distinct voice and speaking style.

## Current Architecture

```
TTSOutputPlugin (tts_plugin.py)
  ├── TTSScriptEngine (tts_script_engine.py)
  │     └── DebateArtifact → TTSScript (segments with voice_id, text)
  └── EdgeTTSRenderer (edge_tts_renderer.py)
        └── edge_tts.Communicate(text, voice) → .mp3 per segment
        └── ffmpeg concat → final audio
```

Key components:
- [`TTSPluginConfig`](backend/services/output/plugins/tts_plugin.py:34): `engine`, `voice_mapping`, `default_voice`, `segment_pause_ms`, `output_format`
- [`TTSSegment`](backend/services/output/plugins/tts_models.py:8): `voice_id`, `text`, `speaker_name`, `speaker_role`
- [`VoiceStore`](backend/services/output/plugins/voice_store.py:20): SQLite cache of edge-tts voices
- [`EdgeTTSRenderer`](backend/services/output/plugins/edge_tts_renderer.py:24): Renders segments via edge-tts + ffmpeg concat

## Target Architecture

```
TTSOutputPlugin (tts_plugin.py)
  ├── TTSScriptEngine (tts_script_engine.py)
  │     └── DebateArtifact → TTSScript (segments with voice_id, text, style_hint)
  │
  ├── EdgeTTSRenderer (edge_tts_renderer.py)        ← existing
  │     └── edge_tts.Communicate → .mp3 per segment
  │
  └── MiMoTTSRenderer (mimo_tts_renderer.py)        ← NEW
        └── OpenAI-compatible /v1/chat/completions
        │     user: style_hint (natural language)
        │     assistant: text (target speech)
        │     audio: { format: "wav", voice: voice_id }
        └── base64 decode → .wav per segment
        └── ffmpeg concat → final audio
```

## MiMo TTS API Contract

```python
# Request (OpenAI-compatible)
POST https://api.xiaomimimo.com/v1/chat/completions
Headers: api-key: $MIMO_API_KEY, Content-Type: application/json
{
    "model": "mimo-v2.5-tts",
    "messages": [
        {"role": "user", "content": "Sharp, analytical tone. Slightly skeptical."},  # style control
        {"role": "assistant", "content": "The argument presented has several logical gaps..."}  # target text
    ],
    "audio": {
        "format": "wav",
        "voice": "Chloe"  # Mia, Chloe, Milo, Dean
    }
}

# Response
{
    "choices": [{
        "message": {
            "audio": {
                "data": "<base64-encoded-wav>"
            }
        }
    }]
}
```

**Call Rules:**
- Target text MUST be in `assistant` role message
- Style/instructions go in `user` role message (optional)
- `audio.format` must be `pcm16` for streaming, `wav` for non-streaming
- `audio.voice` is the built-in voice name

**Built-in Voices (English):**
| Voice | Gender |
|-------|--------|
| Mia | Female |
| Chloe | Female |
| Milo | Male |
| Dean | Male |

## Changes

### Phase 1: MiMo TTS Renderer

**New file:** [`backend/services/output/plugins/mimo_tts_renderer.py`](backend/services/output/plugins/mimo_tts_renderer.py)

```python
class MiMoTTSRenderer:
    """Renders TTSScript to audio via MiMo-V2.5-TTS API."""

    def __init__(self, api_base: str, api_key: str, model: str = "mimo-v2.5-tts"):
        ...

    async def render(self, script: TTSScript, ...) -> Path:
        """Same interface as EdgeTTSRenderer.render()."""
        for segment in script.segments:
            wav_bytes = await self._render_segment(
                text=segment.text,
                voice=segment.voice_id,      # "Mia", "Chloe", etc.
                style_hint=segment.style_hint, # natural language style
            )
            # Save as .wav, generate silence, concat via ffmpeg
```

**Key implementation details:**
- Uses `httpx.AsyncClient` (same as `_generate_local` in LLMService)
- `api-key` header (MiMo uses `api-key` instead of `Authorization: Bearer`)
- Decodes `message.audio.data` from base64 to WAV bytes
- Reuses ffmpeg silence generation and concatenation from `EdgeTTSRenderer` (extract to shared helper)

### Phase 2: Engine Router + Config

**Modified:** [`backend/services/output/plugins/tts_plugin.py`](backend/services/output/plugins/tts_plugin.py)

```python
class TTSEngine(StrEnum):
    EDGE_TTS = "edge_tts"
    MIMO_TTS = "mimo_tts"        # NEW

class TTSPluginConfig(BaseModel):
    engine: TTSEngine = TTSEngine.EDGE_TTS
    # ... existing fields ...

    # MiMo-specific (only used when engine="mimo_tts")
    mimo_api_key_env: str = Field(
        default="MIMO_API_KEY",
        description="Environment variable containing MiMo API key",
    )
    mimo_api_base: str = Field(
        default="https://api.xiaomimimo.com/v1",
        description="MiMo TTS API base URL",
    )
    mimo_model: str = Field(
        default="mimo-v2.5-tts",
        description="MiMo TTS model ID",
    )
    default_style_hint: str = Field(
        default="",
        description="Default style hint for MiMo TTS (natural language)",
    )
```

**Modified:** `TTSOutputPlugin.render()` — select renderer based on `config.engine`:

```python
if config.engine == TTSEngine.MIMO_TTS:
    renderer = MiMoTTSRenderer(api_base=..., api_key=..., model=...)
else:
    renderer = EdgeTTSRenderer()
```

### Phase 3: Style Hints on TTSSegment

**Modified:** [`backend/services/output/plugins/tts_models.py`](backend/services/output/plugins/tts_models.py)

```python
class TTSSegment(BaseModel):
    # ... existing fields ...
    style_hint: str = ""  # NEW: natural language style for MiMo TTS
```

**Modified:** [`backend/services/output/plugins/tts_script_engine.py`](backend/services/output/plugins/tts_script_engine.py)

Add role-type-based default style hints:

```python
ROLE_STYLE_HINTS = {
    "strategist": "Confident, structured delivery. Measured pace with emphasis on key points.",
    "critic": "Sharp, analytical tone. Slightly skeptical. Questions assumptions.",
    "optimizer": "Enthusiastic, solution-oriented. Faster pace, forward energy.",
    "moderator": "Calm, authoritative. Neutral tone with clear transitions between speakers.",
    "fact-checker": "Precise, careful delivery. Methodical pacing.",
    "expert-reviewer": "Knowledgeable, thorough. Professional tone with technical confidence.",
}
```

Each segment gets `style_hint` from `ROLE_STYLE_HINTS.get(segment.speaker_role, "")`.

### Phase 4: Per-Agent Voice Assignment

**Goal:** Each agent persona gets a configurable voice that persists in the blueprint system.

#### 4a. Add `tts_voice_id` field to AgentBlueprint

**Modified:** [`backend/blueprints/models.py`](backend/blueprints/models.py:331)

```python
class AgentBlueprint(BaseModel):
    # ... existing fields ...
    tts_voice_id: str | None = None  # e.g. "Chloe", "Milo", "de-DE-KatjaNeural"
```

**Modified:** [`backend/blueprints/migrations.py`](backend/blueprints/migrations.py)

Migration v15: `ALTER TABLE agent_blueprints ADD COLUMN tts_voice_id TEXT`

#### 4b. Populate voice_mapping from blueprints

**Modified:** `TTSOutputPlugin.render()` — build `voice_mapping` from blueprint data:

```python
# If voice_mapping is empty, try to resolve from blueprints
if not config.voice_mapping:
    from backend.blueprints.repository import BlueprintRepository
    repo = BlueprintRepository()
    for agent in artifact.agents:
        bp = repo.get_blueprint(agent.blueprint_id)
        if bp and bp.tts_voice_id:
            config.voice_mapping[agent.name] = bp.tts_voice_id
```

#### 4c. Frontend: Voice selector in AgentBlueprint inspector

**Modified:** [`frontend/src/components/blueprint/forms/AgentBlueprintForm.svelte`](frontend/src/components/blueprint/forms/AgentBlueprintForm.svelte)

Add a voice selector dropdown:
- When `engine === "edge_tts"`: Show edge-tts voices from `/api/v1/tts-voices`
- When `engine === "mimo_tts"`: Show MiMo voices (Mia, Chloe, Milo, Dean)

#### 4d. Frontend: Voice selector in Config UI Agent Personas

**Modified:** [`frontend/src/views/ConfigView.svelte`](frontend/src/views/ConfigView.svelte)

Add voice badge to agent persona cards (similar to 🧩 blueprint badge).

### Phase 5: Refactor Shared Audio Helpers

**Goal:** Extract ffmpeg silence/concat helpers from `EdgeTTSRenderer` into a shared module.

**New file:** [`backend/services/output/plugins/audio_helpers.py`](backend/services/output/plugins/audio_helpers.py)

```python
async def generate_silence(duration_ms: int, output_path: Path, ffmpeg: str) -> None: ...
async def concat_audio(concat_file: Path, output_path: Path, ffmpeg: str, bitrate: str) -> None: ...
async def decode_base64_audio(b64_data: str, output_path: Path) -> None: ...
```

Both `EdgeTTSRenderer` and `MiMoTTSRenderer` import from this module.

## Data Model Changes

| Table | Column | Type | Default | Notes |
|-------|--------|------|---------|-------|
| `agent_blueprints` | `tts_voice_id` | `TEXT` | `NULL` | MiMo voice name or edge-tts voice ID |
| `tts_voices` | (existing) | — | — | Edge-tts voices; MiMo voices are hardcoded |

## API Changes

| Endpoint | Change | Notes |
|----------|--------|-------|
| `POST /sessions/{id}/render` | `config.engine` can be `"mimo_tts"` | Existing endpoint, new config option |
| `GET /tts-voices` | Add `?engine=mimo_tts` param | Returns MiMo voices when engine=mimo_tts |
| `PUT /blueprints/agent-blueprints/{id}` | `tts_voice_id` field | Existing endpoint, new optional field |

## Edge Cases

| Scenario | Handling |
|----------|----------|
| MiMo API key not set | Graceful fallback to edge-tts with warning |
| MiMo API timeout | Retry once, then fail segment with silence |
| Invalid voice name | Use `mimo_default` fallback |
| Very long text (>5000 chars) | Split into chunks, render separately, concat |
| Mixed engine (edge + mimo) | Not supported — one engine per render job |
| No voice_mapping | Use `default_voice` for all segments |

## Implementation Order

1. **Phase 5**: Refactor shared audio helpers (extract from EdgeTTSRenderer)
2. **Phase 1**: MiMo TTS Renderer (core rendering)
3. **Phase 2**: Engine router + config schema
4. **Phase 3**: Style hints on TTSSegment + role-type defaults
5. **Phase 4**: Per-agent voice assignment (model + migration + frontend)
6. Tests + commit

## Scope: What Changes, What Doesn't

| Component | Change? | Notes |
|-----------|---------|-------|
| `MiMoTTSRenderer` | **NEW** | New renderer class |
| `audio_helpers.py` | **NEW** | Extracted from EdgeTTSRenderer |
| `TTSPluginConfig` | **YES** | Add MiMo-specific fields |
| `TTSSegment` | **YES** | Add `style_hint` field |
| `TTSScriptEngine` | **YES** | Add role-type style hints |
| `TTSOutputPlugin.render()` | **YES** | Engine router |
| `EdgeTTSRenderer` | **YES** | Refactor to use shared helpers |
| `AgentBlueprint` model | **YES** | Add `tts_voice_id` field |
| Migration v15 | **YES** | `ALTER TABLE agent_blueprints ADD COLUMN tts_voice_id TEXT` |
| `VoiceStore` | NO | Edge-tts voices stay as-is |
| `output_composer.py` API | **YES** | Add engine param to tts-voices |
| ConfigForm.svelte | NO | Dynamic form handles new fields automatically |
| AgentBlueprintForm.svelte | **YES** | Add voice selector |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MiMo API instability | Medium | High | Fallback to edge-tts, retry logic |
| Audio format incompatibility | Low | Medium | Use WAV (universal), ffmpeg handles conversion |
| Long text chunking | Medium | Medium | Split at sentence boundaries, max 3000 chars per chunk |
| Rate limiting | Low | Medium | Sequential segment rendering (already the case) |
| API key management | Low | Low | Use existing `api_key_env` pattern from LLM profiles |

## Test Plan

1. Unit: `MiMoTTSRenderer._render_segment()` — mock httpx, verify base64 decode
2. Unit: `TTSScriptEngine` — verify `style_hint` populated from role-type defaults
3. Unit: `audio_helpers` — verify silence generation and concat
4. Integration: `TTSOutputPlugin.render()` with `engine=mimo_tts` — mock MiMo API
5. Integration: Voice mapping from AgentBlueprint `tts_voice_id`
6. E2E: Render a debate artifact to WAV via MiMo TTS
