# On-Demand Replacement Plan: Remove systemd, Add Start Scripts & Local Logging

## TL;DR

> **Quick Summary**: Replace 24/7 systemd services with simple on-demand start/stop scripts, local file logging, and manual/cron-able cleanup.
>
> **Deliverables**:
> - `scripts/start.sh` - Start app in background with PID tracking and local logging
> - `scripts/stop.sh` - Stop app via PID file
> - `scripts/status.sh` - Check status and show recent logs
> - `scripts/cleanup.sh` - Run retention cleanup (replaces systemd timer)
> - Updated `scripts/manage.sh` - Remove systemd references
> - Updated `README.md` and `docs/user_manual.md`
>
> **Estimated Effort**: Short
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Create scripts → Update docs → Delete old systemd files

---

## Context

### Current systemd Setup (in `docs/systemd/`)

| File | Purpose | Key Details |
|------|---------|--------------|
| `debate-agent.service` | Main app service | Port 7860, binds 127.0.0.1, logs to journald, restarts on failure |
| `debate-agent.service_v1` | Older version | Similar to above, slightly different path |
| `debate-agent-cleanup.service` | Cleanup oneshot | Runs `PrivacyGuard(retention_days=90).enforce_retention()` |
| `debate-agent-cleanup.timer` | Daily timer | Triggers cleanup service daily |

### Current Logging Setup
- **systemd**: Logs to journald via `StandardOutput=journal`, `StandardError=journal`
- **Trace logs**: JSONL files in `logs/` directory (separate from app logs)
- **Goal**: Redirect Chainlit stdout/stderr to `logs/debate-agent.log`

### Existing Scripts
- `scripts/manage.sh`: Uses systemd (install, status, logs, trace, backup, stop, restart)
- `scripts/setup_dms.sh`: DMS dependency setup
- `scripts/setup_searxng.sh`: SearXNG setup (also has systemd reference)

### References to Update
- `README.md`: Project Structure shows `systemd/` directory
- `docs/user_manual.md`: Project Structure shows `systemd/` directory
- `setup.sh`: Line 14: `mkdir -p logs config/prompts systemd`
- `scripts/manage.sh`: Full systemd-based management script

---

## Work Objectives

### Core Objective
Make the app usable on-demand: user starts when needed, stops when done. No 24/7 server requirement.

### Concrete Deliverables
- `scripts/start.sh` - Background start with PID tracking and local logging
- `scripts/stop.sh` - Graceful stop via PID file
- `scripts/status.sh` - Status check and log viewing
- `scripts/cleanup.sh` - Retention cleanup (manual/cron)
- Updated `scripts/manage.sh` - New usage: `{start|stop|status|logs|cleanup|backup}`
- Updated `README.md` - Remove systemd, add new scripts
- Updated `docs/user_manual.md` - Remove systemd references

### Definition of Done
- [ ] `bash scripts/start.sh` starts app on port 7860 (background)
- [ ] `bash scripts/stop.sh` stops the app gracefully
- [ ] `bash scripts/status.sh` shows running status
- [ ] App logs to `logs/debate-agent.log` (not journald)
- [ ] `bash scripts/cleanup.sh` runs retention cleanup
- [ ] `docs/systemd/` deleted
- [ ] `docs/etc-logrotate.d/` deleted

### Must Have
- PID file at `logs/debate-agent.pid` (for process tracking)
- Log file at `logs/debate-agent.log` (with log rotation via script)
- Port 7860 configurable via environment variable
- Graceful shutdown (SIGTERM, then SIGKILL after timeout)
- Backup functionality preserved in `manage.sh`

### Must NOT Have (Guardrails)
- NO systemd dependencies in final scripts
- NO journald logging (must use local file)
- NO hard-coded paths (use `$PROJECT_DIR` or auto-detection)
- NO require root privileges (user-level scripts only)

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (bash, Chainlit)
- **Automated tests**: NO (shell scripts - manual verification only)
- **Framework**: bash - test script execution

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/on-demand-{N}-{scenario}.txt`.

- **Scripts**: Test with bash - check exit codes, PID file creation, log writing
- **Integration**: Verify Chainlit starts, responds on port 7860, logs to file

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - Script Creation):
├── Task 1: Create scripts/start.sh (background start, PID, logging)
├── Task 2: Create scripts/stop.sh (graceful stop via PID)
├── Task 3: Create scripts/status.sh (check status, show logs)
└── Task 4: Create scripts/cleanup.sh (retention cleanup)

Wave 2 (After Wave 1 - Updates & Cleanup):
├── Task 5: Update scripts/manage.sh (remove systemd, add new commands)
├── Task 6: Update README.md (Quick Start, Project Structure)
├── Task 7: Update docs/user_manual.md (Project Structure)
├── Task 8: Update setup.sh (remove systemd/ directory creation)
└── Task 9: Delete docs/systemd/ and docs/etc-logrotate.d/
```

### Dependency Matrix

- **1-4**: - - 5
- **5**: 1, 2, 3, 4 - 6, 7, 8
- **6**: 5 - 9
- **7**: 5 - 9
- **8**: 5 - 9
- **9**: 5, 6, 7, 8 - (final)

---

## TODOs

> Implementation = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

### Wave 1: Script Creation

- [x] 1. Create `scripts/start.sh` - Background Start with PID & Local Logging

  **What to do**:
  - Create `scripts/start.sh` that:
    - Detects project directory (auto-detect or `$PROJECT_DIR`)
    - Checks if already running (via PID file `logs/debate-agent.pid`)
    - Starts Chainlit in background:
      ```bash
      nohup uv run chainlit run src/ui/chainlit_app.py --port ${PORT:-7860} > logs/debate-agent.log 2>&1 &
      echo $! > logs/debate-agent.pid
      ```
    - Waits briefly, verifies process is running
    - Prints: "✅ Debate-Agent started on port X (PID: Y). Logs: logs/debate-agent.log"
  - Make executable: `chmod +x scripts/start.sh`
  - Port configurable via `PORT` environment variable (default: 7860)

  **Must NOT do**:
  - Do NOT use systemd commands
  - Do NOT log to journald
  - Do NOT hardcode project directory (use auto-detection)

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple bash script creation with well-defined behavior
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5 (manage.sh update)
  - **Blocked By**: None

  **References**:
  - `docs/systemd/debate-agent.service` - Current startup command to replicate
  - `scripts/manage.sh` - Existing pattern to follow (backup, etc.)

  **Acceptance Criteria**:
  - [ ] `bash scripts/start.sh` starts Chainlit on port 7860
  - [ ] `logs/debate-agent.pid` created with valid PID
  - [ ] `logs/debate-agent.log` receives stdout/stderr
  - [ ] `curl -s <http://127.0.0.1:7860> | head -20` returns HTML

  **QA Scenarios**:

  ```
  Scenario: Start app and verify running
    Tool: Bash
    Preconditions: App not running
    Steps:
      1. Run `bash scripts/start.sh`
      2. Check exit code 0
      3. Verify `logs/debate-agent.pid` exists
      4. Verify `curl -s <http://127.0.0.1:7860> | grep -q "Chainlit"`
    Expected Result: App starts, PID file created, responds on port 7860
    Evidence: `.sisyphus/evidence/on-demand-1-start.txt`

  Scenario: Start when already running
    Tool: Bash
    Preconditions: App running (from Scenario 1)
    Steps:
      1. Run `bash scripts/start.sh`
    Expected Result: Prints "already running" message, does not start second instance
    Evidence: `.sisyphus/evidence/on-demand-1-already-running.txt`
  ```

  **Commit**: YES | Message: `feat: add start.sh for on-demand app startup` | Files: `scripts/start.sh`

- [x] 2. Create `scripts/stop.sh` - Graceful Stop via PID File

  **What to do**:
  - Create `scripts/stop.sh` that:
    - Reads PID from `logs/debate-agent.pid`
    - Sends SIGTERM for graceful shutdown
    - Waits up to 10 seconds for process to exit
    - If still running, sends SIGKILL
    - Removes PID file
    - Prints: "✅ Debate-Agent stopped (PID: X)"
  - Make executable: `chmod +x scripts/stop.sh`

  **Must NOT do**:
  - Do NOT use `systemctl stop`
  - Do NOT force kill immediately (try SIGTERM first)

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple bash script with signal handling
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `scripts/start.sh` (Task 1) - Creates the PID file to read

  **Acceptance Criteria**:
  - [ ] `bash scripts/stop.sh` stops running app
  - [ ] PID file removed after stop
  - [ ] Graceful shutdown (SIGTERM first)

  **QA Scenarios**:

  ```
  Scenario: Stop running app
    Tool: Bash
    Preconditions: App running (from Task 1 QA)
    Steps:
      1. Run `bash scripts/stop.sh`
      2. Verify process not running: `ps -p $(cat logs/debate-agent.pid 2>/dev/null) | grep -v PID`
    Expected Result: App stopped, PID file removed
    Evidence: `.sisyphus/evidence/on-demand-2-stop.txt`

  Scenario: Stop when not running
    Tool: Bash
    Preconditions: App not running, no PID file
    Steps:
      1. Run `bash scripts/stop.sh`
    Expected Result: Prints "not running" message, no error
    Evidence: `.sisyphus/evidence/on-demand-2-not-running.txt`
  ```

  **Commit**: YES | Message: `feat: add stop.sh for graceful app shutdown` | Files: `scripts/stop.sh`

- [x] 3. Create `scripts/status.sh` - Status Check & Log Viewing

  **What to do**:
  - Create `scripts/status.sh` that:
    - Checks if PID file exists and process is running
    - Prints status: "✅ Running (PID: X, Port: Y)" or "⏹ Not running"
    - Shows recent logs (last 20 lines of `logs/debate-agent.log`)
    - Optional: `tail -f` mode if `--follow` flag passed
  - Make executable: `chmod +x scripts/status.sh`

  **Must NOT do**:
  - Do NOT use `systemctl status`
  - Do NOT use `journalctl`

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple bash script for status reporting
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `scripts/manage.sh:14-16` - Existing status command pattern

  **Acceptance Criteria**:
  - [ ] `bash scripts/status.sh` shows correct status (running/not running)
  - [ ] Shows recent log lines

  **QA Scenarios**:

  ```
  Scenario: Status when running
    Tool: Bash
    Preconditions: App running
    Steps:
      1. Run `bash scripts/status.sh`
      2. Verify output contains "Running"
    Expected Result: Status shows running with PID
    Evidence: `.sisyphus/evidence/on-demand-3-status-running.txt`

  Scenario: Status when not running
    Tool: Bash
    Preconditions: App not running
    Steps:
      1. Run `bash scripts/status.sh`
    Expected Result: Status shows "Not running"
    Evidence: `.sisyphus/evidence/on-demand-3-status-stopped.txt`
  ```

  **Commit**: YES | Message: `feat: add status.sh for app status checking` | Files: `scripts/status.sh`

- [x] 4. Create `scripts/cleanup.sh` - Retention Cleanup (Replaces systemd Timer)

  **What to do**:
  - Create `scripts/cleanup.sh` that:
    - Runs: `uv run python -c "from src.core.privacy import PrivacyGuard; PrivacyGuard(retention_days=90).enforce_retention()"`
    - Prints: "✅ Cleanup complete (deleted X old sessions)"
    - Can be run manually or added to crontab:
      ```bash
      # Daily at 2 AM: 0 2 * * * /path/to/scripts/cleanup.sh
      ```
  - Make executable: `chmod +x scripts/cleanup.sh`

  **Must NOT do**:
  - Do NOT use systemd timer
  - Do NOT require root privileges

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple bash wrapper for Python cleanup function
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `docs/systemd/debate-agent-cleanup.service` - Current cleanup command to replicate

  **Acceptance Criteria**:
  - [ ] `bash scripts/cleanup.sh` runs without error
  - [ ] Prints cleanup results

  **QA Scenarios**:

  ```
  Scenario: Run cleanup script
    Tool: Bash
    Steps:
      1. Run `bash scripts/cleanup.sh`
      2. Verify exit code 0
    Expected Result: Cleanup runs, prints results
    Evidence: `.sisyphus/evidence/on-demand-4-cleanup.txt`
  ```

  **Commit**: YES | Message: `feat: add cleanup.sh to replace systemd timer` | Files: `scripts/cleanup.sh`

### Wave 2: Updates & Cleanup

- [x] 5. Update `scripts/manage.sh` - Remove systemd, Add New Commands

  **What to do**:
  - Modify `scripts/manage.sh`:
    - Replace systemd commands with new scripts:
      - `start)`: Call `bash scripts/start.sh`
      - `stop)`: Call `bash scripts/stop.sh`
      - `status)`: Call `bash scripts/status.sh`
      - `logs)`: `tail -f logs/debate-agent.log`
      - Add `cleanup)`: Call `bash scripts/cleanup.sh`
    - Keep existing `backup)` and `trace)` functions
    - Remove: `install)`, `restart)` (or redirect to new scripts)
    - Update usage message

  **Must NOT do**:
  - Do NOT keep systemd references (systemctl, journalctl)
  - Do NOT break backup functionality

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Modify existing bash script, straightforward changes
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 1-4)
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: Tasks 6, 7, 8, 9
  - **Blocked By**: Tasks 1, 2, 3, 4

  **References**:
  - `scripts/manage.sh` (current) - Full modification needed

  **Acceptance Criteria**:
  - [ ] `bash scripts/manage.sh start` works (calls start.sh)
  - [ ] `bash scripts/manage.sh stop` works (calls stop.sh)
  - [ ] `bash scripts/manage.sh status` works (calls status.sh)
  - [ ] `bash scripts/manage.sh cleanup` works (calls cleanup.sh)
  - [ ] Backup function still works

  **QA Scenarios**:

  ```
  Scenario: Manage script start/stop
    Tool: Bash
    Steps:
      1. Run `bash scripts/manage.sh start`
      2. Verify app starts
      3. Run `bash scripts/manage.sh stop`
      4. Verify app stops
    Expected Result: Manage script correctly wraps new scripts
    Evidence: `.sisyphus/evidence/on-demand-5-manage.txt`
  ```

  **Commit**: YES | Message: `refactor: update manage.sh to use new on-demand scripts` | Files: `scripts/manage.sh`

- [x] 6. Update `README.md` - Quick Start & Project Structure

  **What to do**:
  - Modify `README.md`:
    - **Quick Start section**: Replace systemd commands with new scripts:
      ```markdown
      # Start the application (on-demand)
      bash scripts/start.sh
      
      # Check status
      bash scripts/status.sh
      
      # Stop when done
      bash scripts/stop.sh
      ```
    - **Project Structure**: Remove `systemd/` from directory tree
    - Add note: "No systemd required - runs on-demand via simple scripts"

  **Must NOT do**:
  - Do NOT remove DMS, OCR, RAG content (keep all existing features)
  - Do NOT change unrelated sections

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Markdown edit, well-defined changes
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 5)
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8, 9)
  - **Blocks**: Task 9 (delete systemd/)
  - **Blocked By**: Task 5

  **References**:
  - `README.md` (current) - Lines 5-18 (Quick Start), 81-135 (Project Structure)

  **Acceptance Criteria**:
  - [ ] Quick Start shows new scripts (not systemd)
  - [ ] Project Structure removes `systemd/` directory
  - [ ] No broken links or formatting

  **QA Scenarios**:

  ```
  Scenario: Verify README updates
    Tool: Bash
    Steps:
      1. Run `grep -q "scripts/start.sh" README.md`
      2. Run `grep -q "systemd" README.md`
    Expected Result: start.sh found, systemd NOT found (except maybe in docs/ reference)
    Evidence: `.sisyphus/evidence/on-demand-6-readme.txt`
  ```

  **Commit**: YES | Message: `docs: update README for on-demand scripts (remove systemd)` | Files: `README.md`

- [x] 7. Update `docs/user_manual.md` - Project Structure

  **What to do**:
  - Modify `docs/user_manual.md`:
    - **Project Structure section**: Remove `systemd/` from directory tree (around line 81-135)
    - Update to show `scripts/` with new files: `start.sh`, `stop.sh`, `status.sh`, `cleanup.sh`

  **Must NOT do**:
  - Do NOT remove DMS section or other features
  - Do NOT change unrelated content

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Markdown edit, well-defined changes
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 5)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8, 9)
  - **Blocks**: Task 9
  - **Blocked By**: Task 5

  **References**:
  - `docs/user_manual.md` (lines 81-135) - Project Structure section

  **Acceptance Criteria**:
  - [ ] Project Structure removes `systemd/` directory
  - [ ] Project Structure shows new scripts/

  **QA Scenarios**:

  ```
  Scenario: Verify user_manual updates
    Tool: Bash
    Steps:
      1. Run `grep -q "systemd" docs/user_manual.md`
    Expected Result: systemd NOT found in Project Structure (or only in archived docs/ reference)
    Evidence: `.sisyphus/evidence/on-demand-7-manual.txt`
  ```

  **Commit**: YES | Message: `docs: update user_manual for on-demand scripts` | Files: `docs/user_manual.md`

- [x] 8. Update `setup.sh` - Remove systemd/ Directory Creation

  **What to do**:
  - Modify `setup.sh`:
    - Remove `systemd` from `mkdir -p logs config/prompts systemd` (line 14)
    - Update to: `mkdir -p logs config/prompts`

  **Must NOT do**:
  - Do NOT break other setup functionality
  - Do NOT remove other directories

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Single line change in shell script
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 5)
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7, 9)
  - **Blocks**: Task 9
  - **Blocked By**: Task 5

  **References**:
  - `setup.sh` (line 14) - `mkdir -p logs config/prompts systemd`

  **Acceptance Criteria**:
  - [ ] `setup.sh` no longer creates `systemd/` directory
  - [ ] Setup still creates `logs/` and `config/prompts/`

  **QA Scenarios**:

  ```
  Scenario: Verify setup.sh update
    Tool: Bash
    Steps:
      1. Run `grep "mkdir" setup.sh | grep -v "systemd"`
    Expected Result: systemd not in mkdir command
    Evidence: `.sisyphus/evidence/on-demand-8-setup.txt`
  ```

  **Commit**: YES | Message: `refactor: remove systemd from setup.sh` | Files: `setup.sh`

- [x] 9. Delete `docs/systemd/` and `docs/etc-logrotate.d/` Directories

  **What to do**:
  - Delete the archived systemd and etc-logrotate.d directories:
    ```bash
    git rm -r docs/systemd/ docs/etc-logrotate.d/
    ```
  - These are no longer needed since we have new on-demand scripts

  **Must NOT do**:
  - Do NOT delete `scripts/` (new scripts are there)
  - Do NOT delete other files in `docs/`

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple git rm operation
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 6, 7, 8 to update references first)
  - **Parallel Group**: Wave 2 (final task)
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 6, 7, 8 (must update references before deleting)

  **References**:
  - `docs/systemd/` - 4 files to delete
  - `docs/etc-logrotate.d/` - 1 file to delete

  **Acceptance Criteria**:
  - [ ] `docs/systemd/` deleted from repo
  - [ ] `docs/etc-logrotate.d/` deleted from repo
  - [ ] No broken references to these directories

  **QA Scenarios**:

  ```
  Scenario: Verify deletion
    Tool: Bash
    Steps:
      1. Run `ls docs/systemd/ 2>&1 | head -1`
      2. Verify output contains "No such file or directory"
    Expected Result: Directories deleted from repo
    Evidence: `.sisyphus/evidence/on-demand-9-delete.txt`

  Scenario: Verify no broken references after deletion
    Tool: Bash
    Preconditions: Tasks 6, 7, 8 completed (README and manual updated)
    Steps:
      1. Run `grep -r "docs/systemd" README.md docs/user_manual.md`
      2. Verify exit code 1 (no matches found)
    Expected Result: No broken references to deleted directories
    Evidence: `.sisyphus/evidence/on-demand-9-no-broken-refs.txt`
  ```

  **Commit**: YES | Message: `refactor: remove archived systemd and etc-logrotate.d files` | Files: `docs/systemd/`, `docs/etc-logrotate.d/`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Verify All Scripts Work** — `quick`
  - Test: Run `bash scripts/start.sh`, verify app starts on 7860, logs to file
  - Test: Run `bash scripts/stop.sh`, verify app stops, PID file removed
  - Test: Run `bash scripts/status.sh`, verify correct status
  - Test: Run `bash scripts/cleanup.sh`, verify cleanup runs
  - Output: `Scripts [4/4 work] | Logging [OK/FAIL] | PIDs [OK/FAIL] | VERDICT`

- [x] F2. **Verify No systemd References** — `quick`
  - Grep: Search codebase for `systemd`, `journalctl`, `systemctl`
  - Exclude: `docs/` (archived), `README.md` updates
  - Verify: No systemd references in active scripts or docs
  - Output: `systemd refs [N found] | Clean [YES/NO] | VERDICT`

- [x] F3. **Verify Documentation Updates** — `quick`
  - Check: README.md Quick Start shows new scripts
  - Check: README.md Project Structure removes systemd/
  - Check: user_manual.md updated
  - Output: `README [OK/FAIL] | Manual [OK/FAIL] | VERDICT`

- [x] F4. **Integration Test** — `unspecified-high`
  - Start app: `bash scripts/start.sh`
  - Verify: `curl <http://127.0.0.1:7860>` responds
  - Verify: `logs/debate-agent.log` has content
  - Stop app: `bash scripts/stop.sh`
  - Output: `Start [OK/FAIL] | Stop [OK/FAIL] | Logs [OK/FAIL] | VERDICT`

---

## Commit Strategy

- **1**: `feat: add start.sh for on-demand app startup` — `scripts/start.sh`
- **2**: `feat: add stop.sh for graceful app shutdown` — `scripts/stop.sh`
- **3**: `feat: add status.sh for app status checking` — `scripts/status.sh`
- **4**: `feat: add cleanup.sh to replace systemd timer` — `scripts/cleanup.sh`
- **5**: `refactor: update manage.sh to use new on-demand scripts` — `scripts/manage.sh`
- **6**: `docs: update README for on-demand scripts (remove systemd)` — `README.md`
- **7**: `docs: update user_manual for on-demand scripts` — `docs/user_manual.md`
- **8**: `refactor: remove systemd from setup.sh` — `setup.sh`
- **9**: `refactor: remove archived systemd and etc-logrotate.d files` — `docs/systemd/`, `docs/etc-logrotate.d/`

---

## Success Criteria

### Verification Commands
```bash
# Test start script
bash scripts/start.sh
curl -s <http://127.0.0.1:7860> | head -20

# Test stop script
bash scripts/stop.sh

# Test status script
bash scripts/status.sh

# Test cleanup script
bash scripts/cleanup.sh

# Verify no systemd references
grep -r "systemctl\|journalctl" scripts/ README.md docs/user_manual.md
```

### Final Checklist
- [ ] All 4 scripts created and executable
- [ ] App starts on-demand, logs to `logs/debate-agent.log`
- [ ] No systemd dependencies in active code
- [ ] Documentation updated
- [ ] Old systemd files deleted from repo
