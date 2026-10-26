# Cline Rules — Workflow (MUST follow)

## 1. Log every action

- Append a timestamped line to `logs/cline_actions.log` for every meaningful action:
  commands run, files created/edited, results, and errors.
- Format: `YYYY-MM-DDTHH:mm:ss.fff<TAB>message`.
- Use a small PowerShell `Log` helper (see earlier phases) so timestamps are consistent.

## 2. Trash before overwrite

- Before deleting or overwriting ANY existing file, copy the original into
  `trash/<timestamp>_<relative_path>` first.
- Example: `trash/20261026_163050_pyproject.toml`.

## 3. Phase gates

- Work is split into phases. After each phase, print `✅ PHASE <N> COMPLETE`
  and **STOP**.
- Do not start the next phase until the user replies `"continue"`.

## 4. Verify, don't assume

- After every edit, read the file back to confirm the change is what you intended.
- After every build/install, run the smoke or test command.
- Never fabricate tool output, file contents, or test results.

## 5. Git discipline

- Commit at each phase boundary with a clear, conventional message.
- `git push` is **FORBIDDEN**. Local commits only.
- A remote named `origin` may be added, but nothing is ever pushed to it.
- Do not commit `.env`, `trash/`, `logs/`, `output/`, or `reference/`.

## 6. Scope discipline

- Only touch files required by the current phase.
- Never edit `reference/` (read-only upstream) or the external `Zero-K` source tree.
- Keep the fork GPL-2.0-or-later; retain license headers.

## 7. Error handling

- If a required command fails (e.g. editable install), **STOP** and report the
  exact error to the user instead of working around it silently.
