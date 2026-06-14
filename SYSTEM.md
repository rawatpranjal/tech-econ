# SYSTEM.md

*This file is untouchable. It lives in every project and never gets edited inside a project.
It describes the system: the files, the loop, and the rules every skill, subagent, and hook
must follow. If you are an agent working in this folder, read this first, then `CLAUDE.md`.*

## The idea

Every project has the same small set of files. Skills never invent a file. They only read
and write these. Drop this skeleton into any folder and the whole system works the same way
everywhere. The model does the thinking. Cheap local scripts (hooks) do the routing. Git is
the timeline. The files are the dashboard. They move together.

## What the user sees: front-end only

The user's attention is the scarcest resource. The system exists to protect it. The user
thinks about ideas, vision, direction, and the substance of the work, never about the
machinery that runs it. The system is a harness to pull ideas out of the user and turn them
into the right plan; it is not a thing the user operates.

Every skill and subagent keeps two registers apart:
- **Backend, silent.** The files, the YAML, the branches, the hooks, the loop, the
  archiving. None of it is ever narrated to the user.
- **Front-end, what the user reads.** Plain, human-readable talk, like a sharp colleague
  explaining. Ideas, tradeoffs, results, what is worth deciding next. Help the user lean,
  teach themselves, explore, tinker, and decide.

The user never needs to hear the words "SYSTEM.md", "plan.md", "chunk", "hook", "branch", or
a file path. If a sentence to the user is about plumbing, it does not get said. Sweep the
minutia into the back; surface only what helps the user think.

## Surface the vital few (Pareto)

Hiding the machinery is not enough. Among the substance itself, separate the vital few from
the trivial many, and spend the user's attention only on what decides whether the project
wins.

- Know the difference between the **core** (the ideas and decisions that define success) and
  the **minutia** (verification, tedious detail, housekeeping). Handle the minutia silently;
  shepherd the human toward the core.
- The user's attention is the scarcest resource in the system. Spend it only on the
  highest-leverage 20% that drives 80% of the outcome.
- **Rank every deliverable.** Lead with the one thing that matters most, demote the rest,
  bury the housekeeping. Never hand the user a flat list and make them do the prioritizing.
- Point explicitly: "this is what to focus on" versus "this I am handling for you."

## Expand the seed: frame before you plan

The user types little. A short message is a seed, not a literal command. Never lazily execute
the first reading. Before planning any non-trivial work, answer the framing questions in the
backend, then surface only the vital few to the user.

The framing questions: which stage of the project; what was just done and what is ahead; the
higher goal; the immediate goal; what is in and out of scope; the relevant documents; the
questions only the user can answer; the user's underlying intent and preferences; the
contradictions and what is obviously missing; the real options; what needs research (internal
files and external or MCP) and which files to read; the core logic the user should focus on;
the risks and failure modes; which skill to use; which documents to update; which subagents to
launch and at what tier; which tools and MCPs are relevant.

Most of these are answered by **parallel Haiku subagents in the background** reading the
project's own docs, the conversation, and research tools — the user is not asked them. The
`/plan` skill carries this discipline, and a hook forces it whenever planning begins. Surface
to the user only the one or two decisions that genuinely need their judgment, as byte-sized
questions, and only after the background research is done.

## The layout

Seven files at the root, one folder, one sandbox.

| Path | What it holds | Who writes it |
|------|---------------|---------------|
| `SYSTEM.md` | this spec | nobody (read-only) |
| `CLAUDE.md` | high-level instructions and an index to everything below | hand |
| `style.md` | form, visuals, design, layout | hand |
| `roadmap.md` | vision, architecture, full scope, the ordered list of chunks, the done-log | `/roadmap` |
| `status.md` | YAML state plus the handoff for the next session, refreshed each session | skills + hooks |
| `plan.md` | YAML state plus the current chunk: criteria, tasks, verdict, lessons | skills + hooks |
| `decisions.md` | settled answers to recurring questions, so they are never re-asked | hand + `/sim` |
| `docs/` | deeper research and context. Finished plans archive to `docs/plans/` | skills |
| `.claude/simulations/` | gitignored sandbox for throwaway spike scripts, auto-deleted | `/sim` |

`CLAUDE.md` is the home screen: one paragraph on what the project is, links to the other
files, and only the rules unique to this project. The behavior rules live in the global
`~/.claude/CLAUDE.md`. This file (`SYSTEM.md`) is the same in every project.

## The work loop

```
explore -> roadmap -> plan (tests first) -> build -> verify (fresh agent) -> postmortem -> next
                                              ^                            |
                                              |________ fails, back _______|
```

Explore gathers ideas, internal and external. The roadmap captures the scope. The plan
breaks off one chunk and writes its tests first. The work gets built. A separate agent
verifies it against those tests. If it fails, it goes back. The postmortem records what was
learned, saved with the archived plan. Then the next chunk begins.

## Slower on purpose: test first, verify always

One rule runs underneath the whole loop, and it is worth the time it costs.

**Write the test before the work.** Every chunk starts by writing down how we will know it
is right: the acceptance criteria, the tests, the checks. That goes into `plan.md` first,
before any code or prose, then it is frozen with a fingerprint. The goalposts cannot move
after the fact if they were set first.

**Nothing is done until it is verified.** A chunk is never finished on the writer's word. It
has to pass a verification step. For code that means the tests pass and an adversarial pass
finds nothing real. For research it means the claims are checked against sources.

**The writer is never the verifier.** The agent that built something cannot be the one that
signs off on it. The verifier starts fresh, sees only the frozen criteria and the artifact,
not the writer's reasoning, and is asked to break it rather than bless it. This is the same
reason a journal referee is not the author. Someone grading their own work grades it kindly.

This makes the work slower. That is the point. The speed lost is bought back by not shipping
things that quietly do not work.

This is not optional and it is not only for code chunks. Every substantive piece of work, a
merge, a refactor, an analysis, a non-trivial document, any claim that something is done or
correct, gets checked by a separate fresh subagent that tries to break it before it is
reported done. The builder never certifies its own work. No exceptions, no "I'm sure it's
fine."

## Git is the timeline: one chunk, one branch

A chunk in `roadmap.md` maps to exactly one feature branch and one lifecycle of `plan.md`.

1. **Explore and roadmap.** You are on `main`. Run `/explore` and `/sim`, update and commit `roadmap.md`.
2. **Plan and build.** A hook creates `feat/<chunk-id>`. The plan is written. The builder commits its progress to that branch.
3. **Verify.** The verifier checks the branch. If it fails, the builder commits fixes.
4. **Postmortem and archive.** The chunk passes. `/postmortem` writes the lessons. A hook archives `plan.md`, merges the branch into `main`, deletes it, and the cycle repeats.

The working files are the dashboard. Git is the ledger. Because every archived plan is
stamped with the commit it was written against, you can always `git checkout <hash>` and see
the exact code the plan describes.

## The YAML state machine: the router

`status.md` and `plan.md` carry a strict YAML block at the top. Cheap local hooks read that
YAML to move the work from state to state. No model is asked to parse anything.

```yaml
---
chunk_id: "04-aipw-coverage"
builder: "sonnet"
verifier: "opus"
status: "building"   # planning | building | pending_verification | rejected | verified | blocked
strike_count: 0
criteria_fingerprint: "sha256:..."   # set when the criteria freeze; a mismatch halts the loop
branch: "feat/04-aipw-coverage"
archived_commit: null
---
```

The states and what moves them:

| from | trigger | to | hook action |
|------|---------|----|-------------|
| planning | criteria frozen and fingerprinted | building | create `feat/<id>` |
| building | builder sets `pending_verification` | pending_verification | wake the fresh verifier |
| pending_verification | verifier passes | verified | postmortem, archive, merge, advance |
| pending_verification | verifier fails | rejected | strike_count +1; under 3 back to building with feedback; at 3 to blocked |
| blocked | (halt) | (halt) | notify the human and stop the loop |

LLMs write YAML perfectly, so the handoff to the dumb scripts is reliable. The transitions
are deterministic, not a matter of the model's judgment.

## The four mechanisms that make it safe

1. **YAML state.** The single source of truth the hooks route on. Scaffolded into `plan.md` and `status.md` by `/roadmap init`.
2. **The 3-strike circuit breaker.** On a rejection a hook increments `strike_count`. At three it sets `status: blocked`, stops the loop, and notifies you. AI agents are stubborn and will brute-force the same failing fix forever; this forces a human to step in, reset the count to zero, and give a hint. It is the safety valve against a runaway bill.
3. **Git-anchored archiving.** When a chunk is verified, a hook stamps the current commit hash into the plan, moves it to `docs/plans/`, and starts a fresh `plan.md`. Zero tokens, total traceability.
4. **`/sim`.** A time-boxed experiment during the explore phase. It writes a throwaway script into the gitignored `.claude/simulations/` sandbox, runs it, reads the result, records the conclusion in `decisions.md` and `roadmap.md`, then deletes the script. It tests an assumption before the roadmap locks it in, and keeps messy test junk out of the clean codebase.

## /autoloop: the engine

`/autoloop` walks the roadmap on its own, one chunk at a time, through the full loop, with as
little human input as the work allows. It picks the next unfinished chunk, scaffolds the
plan's YAML, and kicks off the builder. From there the hooks route the state. It self-paces
between chunks, and it stops cleanly at any human checkpoint or any failure it cannot clear.
Because all state lives in these files, `/autoloop --resume` picks back up with no memory
loss. Its brakes are the strike counter (retries and no-progress) plus a per-run token and
dollar budget. The criteria fingerprint guards against goalpost drift.

## The skills, wired to the files

Each skill reads and writes one canonical file. It never invents a scratch file.

- `/roadmap` writes `roadmap.md`. `/roadmap init` scaffolds a fresh project.
- `/explore` researches, internal files and the web, into `docs/`, and offers roadmap edits.
- `/status` writes `status.md`.
- `/postmortem` writes the lessons into `plan.md` before it is archived.
- `/bullshit` is the fresh verifier. It runs at chunk close, adversarial, against the frozen criteria.
- `/sim` runs in the sandbox during explore.
- `/search`, `/eda`, `/show` write into `docs/`.
- `/slop` and `/humanizer` clean code or prose in place.

## How skills, subagents, and hooks connect

Three layers, gentlest to strongest.

1. **Skills follow the map by convention.** Each reads `CLAUDE.md` to find the files, pulls what it needs, and writes back to its one assigned file.
2. **Subagents inherit the map from their parent.** A subagent only knows what it is told. The skill hands it the paths it needs; the subagent returns its result to the parent, which writes the canonical file. The writer and the verifier are always different subagents.
3. **Hooks enforce the map automatically.** Hooks are small scripts that fire on events with no reliance on the model remembering anything. They load state at session start, refresh the handoff at session end, block writes outside the canonical files, block sensitive identifiers from anything committed, route the YAML state machine, trip the circuit breaker, and manage the git branches. Skills are "please follow the map." Hooks are "you cannot leave the map."

## Two kinds of memory

- `decisions.md` lives inside the project and travels with it. The "stop asking me this" file: settled choices for this one project. Committed, human-readable, rarely changes.
- The harness keeps its own long-term memory outside the project folder, about how the agent works with the user across every project. It updates rarely and on purpose. There is never a second file named after it inside the project.
