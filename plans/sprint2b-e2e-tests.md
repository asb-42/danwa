# Sprint 2b: Playwright E2E Tests

## Goal
Automated end-to-end tests for all critical user flows. Tests run against the running FastAPI backend (not mocked).

## Acceptance Criteria
- `npx playwright install` installs browsers
- `npm run test:e2e` runs all tests
- `npm run test:e2e:headed` shows visual execution
- All 4 views have at least 3 tests each
- Backend integration tested (not mocked)
- CI pipeline with GitHub Actions (optional)

## Directory Structure (extension)

```
frontend/
├── package.json              # Extended with Playwright
├── playwright.config.js
├── tests/
│   └── e2e/
│       ├── setup.js          # Shared test setup
│       ├── health.spec.js    # Backend connection
│       ├── navigation.spec.js # Hash router
│       ├── debate.spec.js    # Debate flow
│       ├── audit.spec.js     # Audit view
│       ├── config.spec.js    # Config form
│       └── helpers.js        # Reusable helpers
```

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `health.spec.js` | 2 | API health endpoint, frontend status indicator |
| `navigation.spec.js` | 6 | Default view, sidebar nav, back button, active state |
| `debate.spec.js` | 5 | Create debate, agent progression, consensus, empty case, multiple debates |
| `audit.spec.js` | 3 | Table render, agent badges, navigate from debate |
| `config.spec.js` | 3 | Fields present, save action, validation |
| **Total** | **19** | |

## Key Design Decisions

- Tests run against `http://localhost:8000` (FastAPI, not Vite dev server)
- `webServer` config starts Docker Compose for CI
- `reuseExistingServer: !process.env.CI` for local dev
- Chromium + Firefox projects
- Screenshots on failure, video on failure, trace on retry

## CI/CD (GitHub Actions)

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci && npx playwright install --with-deps
      - run: docker-compose up -d && npx wait-on http://localhost:8000/health --timeout 60000
      - run: cd frontend && npx playwright test
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: playwright-report, path: frontend/playwright-report/ }
```

## Deliverables

- [ ] `npx playwright install` installs browsers
- [ ] `npm run test:e2e` runs all tests
- [ ] `npm run test:e2e:headed` shows visual execution
- [ ] All 4 views have at least 3 tests
- [ ] Backend integration tested (not mocked)
- [ ] CI pipeline with GitHub Actions (optional)
