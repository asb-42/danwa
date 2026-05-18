# Impact Analysis: Node.js Upgrade 18 → 22

## Current State
- **Installed**: Node.js v18.19.1, npm 9.2.0
- **Required by GitNexus CLI**: Node.js >=22.0.0

## Dependency Compatibility

| Package | Current Version | Min Node.js | Node 22 Compatible |
|---------|----------------|-------------|-------------------|
| vite | ^5.0.0 | >=18 | ✅ Yes |
| svelte | ^5.0.0 | >=18 | ✅ Yes |
| @sveltejs/vite-plugin-svelte | ^4.0.0 | >=18 | ✅ Yes |
| vitest | ^1.6.1 | >=18 | ✅ Yes |
| @playwright/test | ^1.59.1 | >=18 | ✅ Yes |
| tailwindcss | ^3.4.0 | >=18 | ✅ Yes |
| postcss | ^8.4.0 | >=18 | ✅ Yes |
| elkjs | ^0.11.1 | >=18 | ✅ Yes |
| marked | ^18.0.3 | >=18 | ✅ Yes |
| zod | ^4.4.2 | >=18 | ✅ Yes |

## Code Impact

### Frontend Code
- **`process.env` usage**: Only in `playwright.config.js` (CI detection) — ✅ Compatible
- **No `global.`, `__dirname`, `__filename` usage** — ✅ ESM-only, no Node.js-specific globals
- **`"type": "module"`** in package.json — ✅ Already ESM, no CommonJS issues

### Build System
- **Vite 5**: Fully supports Node.js 22, no breaking changes from 18→22
- **Svelte 5 compiler**: No Node.js version-specific behavior
- **Playwright**: Supports Node.js 22, no API changes

### GitNexus CLI
- **gitnexus@1.6.5**: Requires Node.js >=22 ✅ (This is the reason for upgrade)
- **Dependencies**: commander@14, lru-cache@11, cmake-js@8, thread-stream@4 — all require Node.js >=20

## Breaking Changes Node.js 18 → 22

| Change | Impact on Danwa |
|--------|----------------|
| `fetch()` is now stable | ✅ Positive — can use native fetch in Node.js scripts |
| `test` module (Node:test) | ✅ No impact — not used |
| `import.meta.resolve()` | ✅ No impact — not used |
| Web Crypto API stable | ✅ No impact — not used |
| V8 engine update | ✅ Positive — better performance |
| Removed `--experimental-` flags for many features | ✅ Positive — cleaner CLI |

## Risk Assessment

| Category | Risk | Notes |
|----------|------|-------|
| **Build System** | 🟢 LOW | Vite 5, Svelte 5, all deps support Node.js 22 |
| **Runtime Code** | 🟢 LOW | No Node.js-specific APIs used |
| **Test Suite** | 🟢 LOW | Playwright, Vitest support Node.js 22 |
| **GitNexus CLI** | 🟢 POSITIVE | Will work after upgrade (currently blocked) |
| **npm packages** | 🟢 LOW | All engine constraints satisfied |

## Recommendation

**✅ Safe to upgrade.** No code changes required.

### Steps
1. Install Node.js 22 (via nvm, fnm, or system package manager)
2. Run `npm install` in `frontend/` to rebuild native modules
3. Verify: `node --version` → v22.x.x
4. Test: `./manage.sh start fe` → Frontend should work
5. Test: `npx gitnexus wiki` → Should work without engine warnings

### Rollback
- Keep Node.js 18 installed (via nvm/fnm)
- Switch back: `nvm use 18` or `fnm use 18`
- No code changes to revert

## Files to Update (Optional)
- `.nvmrc` or `.node-version` — pin Node.js version for team consistency
- `frontend/package.json` — add `"engines": {"node": ">=22"}` (optional)
- `manage.sh` — add Node.js version check in `start_frontend()`
