# Sprint 2c: Extended Tests — API Contracts + Visual Regression

## Goal
Ensure API responses match expected schemas (contract tests) and detect unintended visual side effects (visual regression tests).

## API Contract Tests

### Purpose
Validate that FastAPI responses exactly match expected schemas. Prevents frontend breakage from backend API changes.

### Technology
- **Zod** for runtime schema validation (mirrors Pydantic models on frontend side)
- Schemas stay in sync with backend Pydantic models

### Test Coverage

| Test | Endpoint | Schema |
|------|----------|--------|
| Create debate | `POST /api/v1/debate` | `DebateResponseSchema` |
| Get debate status | `GET /api/v1/debate/{id}` | `DebateStatusSchema` |
| Audit events | `GET /api/v1/audit/{id}` | `AuditEventSchema[]` |
| Error responses | `GET /api/v1/debate/invalid-uuid` | `{ detail: string }` |

### Schemas (Zod)

```javascript
const DebateResponseSchema = z.object({
  debate_id: z.string().uuid(),
  status: z.enum(['pending', 'running', 'completed', 'failed']),
  created_at: z.string().datetime()
});

const DebateStatusSchema = z.object({
  debate_id: z.string().uuid(),
  status: z.string(),
  current_round: z.number().int().min(0),
  consensus_score: z.number().min(0).max(1).nullable()
});

const AuditEventSchema = z.object({
  id: z.string().uuid(),
  debate_id: z.string().uuid(),
  round: z.number().int().min(1),
  agent: z.enum(['strategist', 'critic', 'optimizer', 'moderator']),
  action: z.string(),
  timestamp: z.string().datetime(),
  input_hash: z.string(),
  output_hash: z.string(),
  llm_model: z.string(),
  tokens_used: z.number().int().min(0)
});
```

## Visual Regression Tests

### Purpose
Detect unintended visual side effects from UI changes. Compares screenshots pixel-accurately.

### Technology
- Playwright's built-in `toHaveScreenshot()` matcher
- Baseline snapshots stored in `tests/e2e/snapshots/`
- `maxDiffPixels` tolerance for animated content (SSE)

### Test Coverage

| Test | View | Baseline |
|------|------|----------|
| Dashboard default | Dashboard | `dashboard-default.png` |
| Dashboard error state | Dashboard | `dashboard-error.png` |
| Empty debate form | Debate | `debate-empty.png` |
| Debate in progress | Debate | `debate-running.png` |
| Debate completed | Debate | `debate-completed.png` |
| Audit table with data | Audit | `audit-with-data.png` |
| Mobile viewport | Dashboard | `dashboard-mobile.png` |
| Tablet viewport | Debate | `debate-tablet.png` |

### Snapshot Management

```bash
# Create baselines (first run)
npm run test:e2e -- --update-snapshots

# Compare against baselines
npm run test:e2e

# Update specific view
npx playwright test tests/e2e/visual/dashboard.visual.spec.js --update-snapshots
```

## Directory Structure (extension)

```
frontend/tests/e2e/
├── contracts/
│   └── debate.contract.spec.js   # API schema validation
├── visual/
│   ├── dashboard.visual.spec.js  # Dashboard screenshots
│   ├── debate.visual.spec.js     # Debate screenshots
│   ├── audit.visual.spec.js      # Audit screenshots
│   └── responsive.visual.spec.js # Mobile/tablet screenshots
└── snapshots/                    # Baseline screenshots (git-tracked)
    ├── dashboard-default/
    ├── debate-empty/
    └── ...
```

## Extended package.json Scripts

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:headed": "playwright test --headed",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:update-snapshots": "playwright test --update-snapshots",
    "test:contracts": "playwright test tests/e2e/contracts/",
    "test:visual": "playwright test tests/e2e/visual/"
  }
}
```

## CI/CD with Snapshot Upload

```yaml
- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-results
    path: |
      frontend/playwright-report/
      frontend/test-results/

- name: Upload failed snapshots
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: failed-snapshots
    path: frontend/tests/e2e/snapshots/**/diff.png
```

## Deliverables

- [ ] `npm run test:contracts` validates API schemas
- [ ] `npm run test:visual` compares screenshots
- [ ] Baseline snapshots for all 4 views + responsive
- [ ] Zod schemas synchronized with backend Pydantic models
- [ ] CI pipeline detects visual regressions automatically
