# Skills available to the implementing agent

Checked 18 Nov 2026 on PC-D.

| Skill | Status | Used for |
|---|---|---|
| impeccable | **Present**: project scope, `.claude/skills/impeccable` plus 4 helper agents in `.claude/agents/`; engine 0.1.24; no hooks; telemetry off | UI shaping, critique, audit and polish (`DESIGN.md` section 11); the slop detector |
| superpowers | **Missing.** The user must run `/plugin marketplace add obra/superpowers-marketplace` and `/plugin install superpowers@superpowers-marketplace`, then restart Claude Code | Plan execution, TDD, debugging and verification discipline. Until it is installed, the same discipline is followed by hand. |
| humanizer | **Missing.** The user must run `/plugin marketplace add blader/humanizer` and `/plugin install humanizer@humanizer` (Claude Code 2.1.142 or newer), then restart | Prose clean-up of docs, help text and the report (M10, M12) |
| simplify, code-review | Present (built into Claude Code) | Backend clean-up (Task 10.4) |
