# CallLens workspace rules

- At the start of every session, read `docs/BRIEF.md` and `docs/HANDOVER.md`.
- `docs/BRIEF.md` is the project source of truth. If another instruction conflicts, stop and report the conflict.
- Never open, print, echo, copy, edit, stage, or commit `.env` or secret values. Application code may load the key with `python-dotenv`; do not inspect the file contents.
- Never make a live Gnani API call unless the user explicitly replies `go` at the current gate.
- All Gnani calls must pass through `calllens/gnani_client.py::call`.
- Do not delete user data, caches, or existing files. Do not use destructive shell commands. Never `git push`.
- Do not install unapproved dependencies or use unapproved network hosts.
- Before every commit, show `git status --short` and verify that secrets, datasets, audio, caches, and databases are not staged.
- After every milestone, update `docs/HANDOVER.md` and `docs/ASSUMPTIONS.md`.
- Show real command output. Never claim a test, API call, benchmark, or security control succeeded without evidence.
- Maximum three attempts to fix one failure; then stop and document the blocker.
