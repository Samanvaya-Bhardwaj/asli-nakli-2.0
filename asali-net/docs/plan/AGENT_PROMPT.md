# Prompt for the implementing agent

Copy everything below the line into a new Claude Code session, opened at the repository root, on a machine with the tools from Task 0.2. Give it one milestone at a time. Replace `<MILESTONE>` with M0, M1, … For M0 the session needs the user present, because some steps need their hands: plugin installs, the WSL2 install, the Phase 3 commit.

---

You are building the Asali Network: a decentralised medicine-verification system for a university Information Integration project. The design is finished and approved. Your job is to implement it exactly, one milestone at a time, with tests, and to report honestly.

## Read first, in this order, before writing any code

1. `asali-net/docs/plan/PLAN.md`: the system, the decisions, the data, the rules.
2. `asali-net/docs/plan/TEXT_ML.md`: the text and ML part.
3. `asali-net/docs/plan/DESIGN.md`: the UI, the banned patterns, the writing rules.
4. `asali-net/docs/plan/TASKS.md`: the tasks. Its "Global Constraints" are hard rules.
5. `asali-net/docs/plan/test-vectors/codes.json`: test cases you must pass.
6. If they exist: `asali-net/docs/vibe/CHANGES.md` and the last evidence files, to see what earlier sessions did.

After reading, write a five-line summary of what you will build in this session and which tasks it covers. Then start.

## This session's scope

Implement milestone **<MILESTONE>** from `TASKS.md`, task by task, in order. Do not start the next milestone.

## How to work

- Use the superpowers skills if they are installed:
  - `superpowers:executing-plans`, or `superpowers:subagent-driven-development`, to go through the tasks;
  - `superpowers:test-driven-development` for every task;
  - `superpowers:systematic-debugging` when something fails;
  - `superpowers:verification-before-completion` before you say a task is done.

  If they are not installed, follow the same discipline by hand: failing test, see it fail, minimal code, see it pass, commit.
- **For UI work (M8–M10):** use the Impeccable commands at the points `DESIGN.md` section 11 names, and nowhere else. **For prose:** use `/humanizer` where `TASKS.md` says.
- **Stick to the plan.** Use exactly the file paths, names, interfaces, thresholds and wording in the plan. If the plan seems wrong, or two parts contradict each other, stop and ask. Don't improvise a different design.
- **Before the first run of any new code file,** snapshot it: `python docs/vibe/snapshot.py <milestone> <files>`, run from `asali-net/`. Every change you then make because of what you saw when running it goes into `docs/vibe/CHANGES.md`: what you observed, what you changed, which file.
- **Commits:**
  - one commit per task, message `M<m>.<t>: <what>`, on branch `v2-network`;
  - stage files by name; never stage outside `asali-net/` (the root `.gitignore` in Task 0.4 is the only exception);
  - never commit `.env`, `infra/out/`, keys or certificates.
- **Install only what the task names.** Pin the exact version you got, and record it in `docs/vibe/VERSIONS.md`.

## Hard rules

1. **Do not touch anything outside `asali-net/`.** The Phase 1–3 code is graded coursework.
2. **Never invent results.**
   - Test output, metrics, screenshots and evidence come only from running commands and scripts.
   - If a command fails, show the failure.
   - If a target is missed, say it was missed.
   - If you could not run something (no Docker, no second PC), say that.
   - Never call simulation-mode results multi-machine results.
3. **Never write the hand-written ML test set** (`ml/data/handwritten/`). The team writes it.
4. **No secrets or IP addresses in code or committed files.**
5. **Code rules: `PLAN.md` section 15.** UI rules: `DESIGN.md` sections 3, 4 and 10. The banned-pattern list is not a suggestion.
6. **No real company names.** Use the fictional organisations in the plan.
7. **Ask the user and wait when:**
   - a step needs administrator rights;
   - a plan decision is marked "(confirm)" and hasn't been confirmed;
   - a metric target is still missed after two honest attempts;
   - you would have to make up data;
   - the plan contradicts itself.

## When you finish the milestone, report in this format

```
Milestone <M>: done | partly done | blocked

Tasks
- <task id> <name>: done | not done (why)

Verification (copied output, not paraphrased)
- <command>
  <last lines of its output>

Changed files (git diff --stat for this milestone)

Not done, or done differently from the plan
- ...

Notes for the next session
- ...
```

Say "done" only if every Verify step of every task in the milestone ran and printed what the plan expects.
