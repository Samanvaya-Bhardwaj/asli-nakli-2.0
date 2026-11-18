# Prompts (vibe-coding record)

Every prompt that produced code in `asali-net/`, verbatim, in order. Spelling is left exactly as typed.

## V2-0: the request that produced the plan (18 Nov 2026)

```text
the project phase 2 feedback from the prof ->
we will have a phama company wise dbs and then shop wise dbs and a distributor wise dbs each db may have different stuctures to store
now all is decentralized and they are giving access to their db as only read only way
now the portal will have few functions lets say if i am a distributor i'll scan the medicine and then add where are we sending then it will save that that distributor have given the medicine to the shop
then again a portal for shop they will scan and insert to whom they are selling
now location wise the shop portal will vary
shop and distributor and phama all have different portals for simplicity we are using same ui for everyportal and for example we will make 2-3 portal for each and we have 4 pcs each will host each type or portal 1(2=3) distributor 1 shops (2 -3 ) and another pharma (2-3) and anotehr user (2-3) now there is part we need to make it unstructured and same time we have to make a real world whole system not a single pc not a single thing a complete whole orchestration we have 4 pcs we can connect

your task is to plan the whole thing
the current ui is too much ai slop
use all use full skills tile superpower and impeccable or other skills to generate plan with de ai slopification plan of the ui and also back end and for text all over the site de ai slop them also with proper plugins or skills
for front end there are many motion libraries and many component libraries you can use the current partal is too much clutered you have to fix it
and during scanning system may have read many wrong characters we need to fix it
first read current implementation and then make a end to end proper detailed plan to make the the whole project from scartch dont assume that you have to build on top of what ever have been implemented
you can take some features or some functions and but mostly you have to to build from scractch
now start your einstein level brain and work hard and make a end to end plan with installing all the skills you need to use and then also make a prompt that will give to lower coding agent that will implement the plan
as the implementing agent have less intelligence you do have to make end to end detailed plan
first understand my idea and start working harddddd
```

Sent while the plan was being written:

```text
also for unstructured data think of what kind of unstructured data we can use -> asked sir sir told dont need to work with the image we can use of text and we can use ml algo and then with the unstructured dat we need to link and verify the medicine with strcutred data include it with the plan also
```

```text
we have 4 pc
1 -> 16gb ram (i7 h series)
1 -> 16gb ram (mac m4)
1 -> 8gb (ryzen 5 u series)
and this one
```

Output: `docs/plan/` (`PLAN.md`, `TEXT_ML.md`, `DESIGN.md`, `TASKS.md`, `AGENT_PROMPT.md`, `test-vectors/codes.json`).

## V2-1: start of implementation (18 Nov 2026)

```text
continue
```

Taken as approval to start building, beginning with M0 (set-up) and M1 (codes). Those two milestones don't depend on the three decisions still marked "(confirm)" in `PLAN.md` section 2.

## V2-2: linter and commits (19 Nov 2026)

```text
why do we need wsl? and yes switch to eslint, go according to the plan as told you
```

Result:
- oxlint was replaced with ESLint (`CHANGES.md` D6).
- Work moved to branch `v2-network`, with one commit per task as `TASKS.md` requires. The Phase 3 changes in the working tree were left uncommitted and untouched.

## Later sessions

Each implementing session uses `docs/plan/AGENT_PROMPT.md` with `<MILESTONE>` filled in. Record each one here, with the milestone it was given.
