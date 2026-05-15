# Enhanced Debate Feedback — Plan (v2)

## Design Philosophy

> Sachlich, elegant, nicht-intrusiv. Information should feel like a natural
> part of the UI, not an afterthought. The user should glance at it and
> instantly know: "The app is working, here's what's happening."

## Visual Design: "Activity Strip"

Instead of a multi-line card with stacked text, we use a **compact activity
strip** — a slim, single-purpose bar between the debate status card and the
timeline. It uses visual hierarchy (size, color, spacing) to separate
information types without walls of text.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ● ● ○ ○   Kritiker analysiert…                                 │
│                                                                  │
│  tencent/hy3-preview:free          ⏱ 3,2s    📊 1.234 Tokens    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Visual Breakdown

**Row 1 — Primary info (larger, prominent)**
- **Progress dots**: 4 small circles (●●○○), filled = completed agents,
  empty = pending, pulsing = active. Colored by role (blue/red/amber/violet).
- **Status text**: "{Role} analysiert…" in the role's accent color.
  Uses i18n verb: "analysiert" (Stratege), "prüft" (Kritiker),
  "optimiert" (Optimierer), "bewertet" (Moderator).

**Row 2 — Secondary info (smaller, muted)**
- **Left**: Model name in `font-mono text-xs text-zinc-500`
- **Right**: Timer + Token counter in pill-shaped badges

### Styling Details

- **Container**: `bg-zinc-900/50 border border-zinc-800 rounded-xl p-4`
  — subtle, doesn't compete with the white cards above/below
- **Progress dots**: `w-2.5 h-2.5 rounded-full` with role-specific colors
  - Completed: solid fill
  - Active: `animate-ping` + solid fill overlay
  - Pending: `bg-zinc-700`
- **Status text**: `text-sm font-medium` in role accent color
- **Pills**: `px-2 py-0.5 rounded-full bg-zinc-800 text-xs text-zinc-400 font-mono`
- **Timer**: Updates every 100ms, shows `X.Xs` format
- **Token counter**: Formatted with locale separator (1.234 or 1,234)

### Color Palette (per role)

| Role | Accent | Dots | Text |
|------|--------|------|------|
| Strategist | `#3b82f6` (blue) | `bg-blue-500` | `text-blue-400` |
| Critic | `#ef4444` (red) | `bg-red-500` | `text-red-400` |
| Optimizer | `#f59e0b` (amber) | `bg-amber-500` | `text-amber-400` |
| Moderator | `#8b5cf6` (violet) | `bg-violet-500` | `text-violet-400` |

### Transitions

- Strip slides in with `transition:fly={{ y: -8, duration: 200 }}` when
  debate starts running
- Status text fades between agents with `transition:fade`
- Token counter uses `transition:slide` for number changes
- Strip slides out when debate completes

### States

1. **Waiting** (debate just started, no agent yet):
   ```
   ● ● ● ●   Warte auf ersten Agent…
   ```

2. **Processing** (LLM call in progress):
   ```
   ● ● ◐ ○   Kritiker analysiert…
   tencent/hy3-preview:free          ⏱ 3,2s    📊 1.234 Tokens
   ```
   (◐ = pulsing active dot)

3. **Between agents** (brief moment after output, before next starts):
   ```
   ● ● ● ○   Kritiker abgeschlossen
   tencent/hy3-preview:free          ⏱ 8,1s    📊 2.456 Tokens
   ```

4. **Round transition** (after all agents in a round):
   ```
   ● ● ● ●   Runde 2 abgeschlossen — Konsens 60%
   ```

5. **Completed** (debate done):
   Strip fades out, replaced by the existing final verdict section.

### i18n Keys

```javascript
// German
'feedback.analysing': '{role} analysiert…',
'feedback.checking': '{role} prüft…',
'feedback.optimizing': '{role} optimiert…',
'feedback.evaluating': '{role} bewertet…',
'feedback.completed': '{role} abgeschlossen',
'feedback.waiting': 'Warte auf ersten Agent…',
'feedback.roundDone': 'Runde {round} abgeschlossen — Konsens {percent}%',
'feedback.processing': 'Verarbeitung',
'feedback.totalTokens': 'Tokens',

// English
'feedback.analysing': '{role} analysing…',
'feedback.checking': '{role} checking…',
'feedback.optimizing': '{role} optimizing…',
'feedback.evaluating': '{role} evaluating…',
'feedback.completed': '{role} completed',
'feedback.waiting': 'Waiting for first agent…',
'feedback.roundDone': 'Round {round} completed — Consensus {percent}%',
'feedback.processing': 'Processing',
'feedback.totalTokens': 'Tokens',
```

### Role-specific verbs

| Role | DE | EN |
|------|----|----|
| Strategist | analysiert | analysing |
| Critic | prüft | checking |
| Optimizer | optimiert | optimizing |
| Moderator | bewertet | evaluating |

## Implementation Steps

### Step 1: Backend — `GenerationResult` dataclass

**File**: `backend/services/llm_service.py`

```python
from dataclasses import dataclass

@dataclass
class GenerationResult:
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""
```

- `_generate_litellm()`: capture `response.usage.prompt_tokens`,
  `response.usage.completion_tokens`, measure wall-clock duration,
  return `GenerationResult`
- `_generate_local()`: estimate tokens from content, measure duration,
  return `GenerationResult`
- `generate()`: return `GenerationResult` instead of `str`

### Step 2: Backend — Enrich SSE events

**File**: `backend/workflow/nodes.py`

1. **`agent_started`** — add `model`, `provider`, `agent_index`, `agent_total`
2. **`agent_output`** — add `tokens_in`, `tokens_out`, `duration_ms`, `model`
3. **`round_update`** — add `total_tokens`

### Step 3: Frontend — Activity Strip component

**File**: `frontend/src/views/DebateView.svelte`

New state variables:
```javascript
let cumulativeTokens = 0;
let processingStartTime = null;
let processingElapsed = 0;
let processingTimer = null;
```

Updated `handleSSEEvent()`:
- `agent_started` → set `currentActivity` with enriched data, start timer
- `agent_output` → stop timer, accumulate tokens, push to `liveOutputs`
- `round_update` → update round info

### Step 4: Frontend — Activity Strip UI

Compact strip between debate status and timeline:
- Row 1: Progress dots + role verb (colored)
- Row 2: Model name + timer pill + token pill

### Step 5: Frontend — Enhanced timeline cards

Add `duration_ms` and token breakdown to existing inline cards.

### Step 6: i18n keys

Add feedback keys to `de.js` and `en.js`.

### Step 7: Tests

Update `test_llm_service.py`, `test_workflow.py`, `test_debate_api.py`.

## Files to Modify

| File | Change |
|------|--------|
| `backend/services/llm_service.py` | `GenerationResult`, real tokens + duration |
| `backend/workflow/nodes.py` | Enrich SSE events |
| `frontend/src/views/DebateView.svelte` | Activity Strip, enhanced handler |
| `frontend/src/lib/i18n/loaders/de.js` | Feedback i18n keys |
| `frontend/src/lib/i18n/loaders/en.js` | Feedback i18n keys |
| `tests/backend/test_llm_service.py` | Update for `GenerationResult` |
| `tests/backend/test_workflow.py` | Update for enriched events |
