# Vibe-coding record

The course asks to see the original prompt, the code it produced, and how that code was changed. This folder keeps all three for `asali-net/`.

| File | What it holds |
|---|---|
| `PROMPTS.md` | Every prompt that produced code, verbatim, in order |
| `generated/<milestone>/` | Each new code file exactly as first written, saved by `snapshot.py` before it ever ran |
| `CHANGES.md` | Every change made after a file first ran: what was observed and what changed. Also every place the work differs from the plan. |
| `VERSIONS.md` | Tools and library versions as installed |
| `SKILLS.md` | Which Claude Code skills were available |
| `DIFFS.md` | Written in M12 by `docs/scripts/vibe_diffs.py`: each snapshot against the current file |

Saving a snapshot, from `asali-net/`:

```
py -3.11 docs/vibe/snapshot.py M2 services/directory/asali_directory/main.py
```

It refuses to overwrite a snapshot that already exists, so the first version is never lost.
