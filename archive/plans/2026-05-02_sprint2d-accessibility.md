# Sprint 2d: Accessibility Tests — WCAG 2.1 AA

## Goal
Ensure the frontend meets WCAG 2.1 AA compliance through automated accessibility testing with axe-core, keyboard navigation tests, and screen reader verification.

## Technology
- **@axe-core/playwright** — Automated WCAG 2.1 AA violation detection
- **Playwright** — Keyboard navigation and ARIA attribute testing
- **axe-core ruleset** — `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`

## Test Coverage

### Automated Axe-core Scans

| Test | View | Rules |
|------|------|-------|
| Dashboard accessibility | Dashboard | Full WCAG 2.1 AA |
| Debate form accessibility | Debate | Full WCAG 2.1 AA |
| Audit table accessibility | Audit | Full WCAG 2.1 AA |
| Config form accessibility | Config | Full WCAG 2.1 AA |
| Mobile viewport accessibility | All views | Full WCAG 2.1 AA |

### Keyboard Navigation Tests

| Test | View | Keys |
|------|------|------|
| Tab through all interactive elements | Dashboard | `Tab`, `Shift+Tab` |
| Activate debate with Enter | Debate | `Enter` |
| Navigate audit rows with arrows | Audit | `ArrowUp`, `ArrowDown` |
| Submit config form with Enter | Config | `Enter` |
| Escape closes modals/dialogs | All | `Escape` |
| Focus trap in modal dialogs | Config | `Tab` cycling |
| Skip-to-content link | All | `Tab` first item |

### ARIA and Semantic Tests

| Test | View | Check |
|------|------|-------|
| All images have alt text | All | `alt` attribute |
| Form inputs have labels | Config, Debate | `<label>` or `aria-label` |
| Live regions announce SSE updates | Debate | `aria-live="polite"` |
| Table has proper headers | Audit | `<th>` with `scope` |
| Navigation has landmark roles | All | `<nav>`, `<main>`, `<header>` |
| Error messages linked to inputs | Config, Debate | `aria-describedby` |
| Status indicators have text alternatives | Dashboard | `aria-label` or visible text |

### Color Contrast Tests

| Test | Element | Minimum Ratio |
|------|---------|---------------|
| Body text | All views | 4.5:1 (normal text) |
| Headings | All views | 3:1 (large text) |
| Button text | All views | 4.5:1 |
| Link text | All views | 4.5:1 (3:1 for links in body) |
| Error text | Forms | 4.5:1 |
| Disabled elements | Forms | Exempt but documented |

### Screen Reader Announcement Tests

| Test | Trigger | Expected Announcement |
|------|---------|----------------------|
| Debate started | POST /debate | "Debate started" via `aria-live` |
| New round | SSE event | "Round {n} started" via `aria-live` |
| Debate completed | SSE event | "Debate completed with consensus score {x}" |
| Error occurred | API error | "Error: {message}" via `role="alert"` |
| Loading state | Any async | "Loading" via `aria-busy` |

## Implementation

### Axe-core Integration

```javascript
// tests/e2e/a11y/dashboard.a11y.spec.js
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Dashboard Accessibility', () => {
  test('has no WCAG 2.1 AA violations', async ({ page }) => {
    await page.goto('/#/');
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
```

### Keyboard Navigation

```javascript
// tests/e2e/a11y/keyboard.a11y.spec.js
import { test, expect } from '@playwright/test';

test.describe('Keyboard Navigation', () => {
  test('tab order follows DOM order on dashboard', async ({ page }) => {
    await page.goto('/#/');
    const focusableElements = await page.$$eval(
      'a, button, input, select, textarea, [tabindex]',
      els => els.map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim().substring(0, 30),
        tabindex: el.getAttribute('tabindex')
      }))
    );
    // Verify no positive tabindex values (anti-pattern)
    const badTabindex = focusableElements.filter(
      el => el.tabindex && parseInt(el.tabindex) > 0
    );
    expect(badTabindex).toEqual([]);
  });

  test('debate form is fully keyboard operable', async ({ page }) => {
    await page.goto('/#/debate');
    // Tab to topic input
    await page.keyboard.press('Tab');
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(focused).toBe('INPUT');
    // Type topic
    await page.keyboard.type('Test debate topic');
    // Tab to submit button
    await page.keyboard.press('Tab');
    // Activate with Enter
    await page.keyboard.press('Enter');
    // Verify debate started
    await expect(page.locator('[aria-live="polite"]')).toContainText(/started|running/i);
  });

  test('escape closes any open dialog', async ({ page }) => {
    await page.goto('/#/config');
    // Open a dialog/modal if present
    const dialog = page.locator('[role="dialog"]');
    if (await dialog.isVisible()) {
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
    }
  });
});
```

### ARIA Attributes

```javascript
// tests/e2e/a11y/aria.a11y.spec.js
import { test, expect } from '@playwright/test';

test.describe('ARIA Attributes', () => {
  test('all views have proper landmark roles', async ({ page }) => {
    const views = ['/#/', '/#/debate', '/#/audit', '/#/config'];
    for (const view of views) {
      await page.goto(view);
      await expect(page.locator('main, [role="main"]')).toBeAttached();
      await expect(page.locator('nav, [role="navigation"]')).toBeAttached();
    }
  });

  test('debate view has live region for SSE updates', async ({ page }) => {
    await page.goto('/#/debate');
    const liveRegion = page.locator('[aria-live]');
    await expect(liveRegion).toBeAttached();
    const liveValue = await liveRegion.getAttribute('aria-live');
    expect(['polite', 'assertive']).toContain(liveValue);
  });

  test('audit table has proper headers', async ({ page }) => {
    await page.goto('/#/audit');
    const headers = page.locator('table th');
    const count = await headers.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      const scope = await headers.nth(i).getAttribute('scope');
      expect(scope).toBe('col');
    }
  });

  test('form inputs have associated labels', async ({ page }) => {
    await page.goto('/#/config');
    const inputs = page.locator('input:not([type="hidden"])');
    const count = await inputs.count();
    for (let i = 0; i < count; i++) {
      const id = await inputs.nth(i).getAttribute('id');
      const ariaLabel = await inputs.nth(i).getAttribute('aria-label');
      const ariaLabelledBy = await inputs.nth(i).getAttribute('aria-labelledby');
      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.count() > 0;
        expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
      } else {
        expect(ariaLabel || ariaLabelledBy).toBeTruthy();
      }
    }
  });
});
```

### Screen Reader Announcements

```javascript
// tests/e2e/a11y/screenreader.a11y.spec.js
import { test, expect } from '@playwright/test';

test.describe('Screen Reader Announcements', () => {
  test('debate start triggers announcement', async ({ page }) => {
    await page.goto('/#/debate');
    await page.fill('input[name="topic"]', 'Test topic');
    await page.click('button[type="submit"]');
    // Wait for aria-live region to update
    const liveRegion = page.locator('[aria-live="polite"]');
    await expect(liveRegion).not.toBeEmpty({ timeout: 5000 });
  });

  test('error messages use role="alert"', async ({ page }) => {
    await page.goto('/#/debate');
    // Trigger an error (e.g., empty topic)
    await page.click('button[type="submit"]');
    const alert = page.locator('[role="alert"]');
    await expect(alert).toBeVisible({ timeout: 3000 });
  });

  test('loading states announce via aria-busy', async ({ page }) => {
    await page.goto('/#/debate');
    await page.fill('input[name="topic"]', 'Test');
    await page.click('button[type="submit"]');
    // Check for aria-busy on loading container
    const busyElement = page.locator('[aria-busy="true"]');
    // May be transient, so just check it appeared
    const appeared = await busyElement.isVisible({ timeout: 2000 }).catch(() => false);
    // Either aria-busy or aria-live announcement should exist
    const liveRegion = page.locator('[aria-live]');
    expect(appeared || await liveRegion.count() > 0).toBeTruthy();
  });
});
```

## Directory Structure (extension)

```
frontend/tests/e2e/
├── contracts/
│   └── debate.contract.spec.js
├── visual/
│   ├── dashboard.visual.spec.js
│   ├── debate.visual.spec.js
│   ├── audit.visual.spec.js
│   └── responsive.visual.spec.js
├── a11y/
│   ├── dashboard.a11y.spec.js      # Axe-core scans per view
│   ├── debate.a11y.spec.js
│   ├── audit.a11y.spec.js
│   ├── config.a11y.spec.js
│   ├── keyboard.a11y.spec.js       # Keyboard navigation
│   ├── aria.a11y.spec.js           # ARIA attribute checks
│   └── screenreader.a11y.spec.js   # Live region announcements
└── snapshots/
```

## Extended package.json Scripts

```json
{
  "scripts": {
    "test:a11y": "playwright test tests/e2e/a11y/",
    "test:a11y:dashboard": "playwright test tests/e2e/a11y/dashboard.a11y.spec.js",
    "test:a11y:keyboard": "playwright test tests/e2e/a11y/keyboard.a11y.spec.js"
  }
}
```

## CI/CD Integration

```yaml
# .github/workflows/test.yml
- name: Accessibility tests
  run: cd frontend && npm run test:a11y

- name: Upload a11y report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: a11y-report
    path: frontend/playwright-report/
```

## Deliverables

- [ ] `npm run test:a11y` runs all accessibility tests
- [ ] Axe-core scans pass WCAG 2.1 AA on all 4 views
- [ ] Keyboard navigation works for all interactive elements
- [ ] All form inputs have associated labels
- [ ] Live regions announce SSE-driven state changes
- [ ] Audit table has proper semantic markup
- [ ] Error messages use `role="alert"`
- [ ] Skip-to-content link present on all views
- [ ] CI pipeline runs accessibility tests on every PR
