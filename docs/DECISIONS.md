# Decision Log — `ask`

The single source of truth. Every decision we've locked in, so the design stays
consistent as we build.

## What it is
| # | Decision |
|---|----------|
| D1 | A self-correcting terminal command assistant (working name `ask`) |
| D2 | Solves: you know *what* you want in the terminal but not the *command*; and cryptic errors leave you stuck |
| D3 | For anyone at a terminal — beginner or expert, daily or rare user |
| D4 | You read command output yourself — the tool does **not** explain results in English |

## How you interact
| # | Decision |
|---|----------|
| D5 | It's an interactive **session** you work inside — not a one-shot command |
| D6 | The session behaves like a **terminal tab** (open → work → close) |
| D7 | Default: anything you type runs as a **raw command** |
| D8 | `/ask <english>` **generates and shows** a command; **you press Enter to run** (or not) |
| D9 | `/debug [optional text]` writes a fix and **shows it**; you press Enter to run; optional text adds context if the AI guesses wrong |
| D10 | `/start` begins a session; `/exit` ends it |
| D11 | Rule: `/` = call the AI; no prefix = run literally |

## How commands run & get fixed
| # | Decision |
|---|----------|
| D12 | Success/failure is judged by **exit code** (0 = passed) |
| D13 | On failure, the **error is fed back** to the AI so the next attempt is smarter |
| D14 | **No automatic loop.** Retry = you typing `/debug` again yourself; one attempt per press |
| D38 | The **human presses Enter** to run anything the AI produces — nothing AI-written auto-executes |

## Risk Score
| # | Decision |
|---|----------|
| D36 | AI-generated commands (`/ask`, `/debug`) show a Risk Score (🟢 Low / 🟡 Medium / 🔴 High) before running |
| D37 | Risk is judged from **the command text only**, not history |
| D39 | Raw commands you type are **not** risk-scored (you wrote them, you own them) |

## Memory & session
| # | Decision |
|---|----------|
| D15 | The command **history** is **in-RAM only, ephemeral** — not saved to disk |
| D16 | Every turn is recorded automatically — raw commands **and** AI commands |
| D17 | Each turn holds: command + output + error + exit code |
| D18 | `/exit` drops the history (reference released → freed); new session = empty history |
| D19 | Storage is effectively unlimited in RAM (text is tiny) |

## State handling — the folder (`cd`) is special
Insight: most commands are **independent** (they do their work and don't affect
later commands), so their history is disposable. But the **current folder**
(`cd`) is *state* that affects every command after it — so it is the one piece
worth tracking and keeping.

| # | Decision |
|---|----------|
| D44 | Each helper process is fresh and stateless, so the OS won't remember the folder between commands — **our program tracks the current folder itself** (in a variable) |
| D45 | Normal commands run in a fresh helper, told where to start via the `cwd` ("current working directory") parameter, set from our tracked folder |
| D46 | `cd` is intercepted: we **don't** spawn a helper, we just **update our folder variable** |
| D47 | The prompt shows the tracked folder (e.g. `ask C:\project\sub>`), updated automatically because it's built from the variable |
| D48 | On `/exit`, we discard the history but **persist only the last folder** (one line to a small file); the next `/start` resumes in that folder — meaningful state is kept, disposable actions are dropped |
| D49 | Keeping one shell alive for full state (env vars, etc.) is a later "real tool" upgrade; for now only the **folder** is tracked/persisted |

## Context (the "note" sent to the AI)
| # | Decision |
|---|----------|
| D20 | Send **small notes** to keep it cheap/fast |
| D21 | Keep only the **last ~5 commands** (a tunable number) |
| D22 | **Trim long output** (~30 lines) before it bloats a note |
| D23 | `/ask` note = environment + your request (little/no history) |
| D24 | `/debug` note = environment + failed command + error + last few commands |
| D25 | All note logic lives in **one Memory box** with `record()` and `build_note()` |

## Environment & tech
| # | Decision |
|---|----------|
| D26 | Targets **Windows + PowerShell first** (not portable yet) |
| D27 | The AI is always told the **environment** (OS/shell) so commands work here |
| D28 | Uses the **Gemini API**, model **Flash** (free tier — good for a student) |
| D40 | Language is **Python 3.13** (chosen to learn it for the AI-engineer path) |
| D41 | SDK is **`google-genai`**; secrets via **`python-dotenv`**; output via **`rich`**; commands via **`subprocess`** |
| D42 | **Simple sync Python** — no FastAPI (it's a CLI, not a web server) and no async (single-user, sequential) |

## Architecture principles
| # | Decision |
|---|----------|
| D29 | **Separation of concerns** — each job in its own box (Session, Memory, Executor, AI/Provider, Config) |
| D30 | Changes should **stay in one box** — the whole reason for the boxes |
| D31 | Goal: eventually **deploy it** and make it industry-standard |
| D43 | Session/CLI depends on the core boxes; core boxes do not depend on the CLI (keeps them testable/swappable) |

## Non-goals (scope)
| # | Decision |
|---|----------|
| D32 | Not a general chatbot |
| D33 | Not an explainer (no narrating results) |
| D34 | Not portable yet (Windows/PowerShell only) |
| D35 | Skip advanced context tricks (no summarization, no RAG) for now |

## Decisions that evolved (final answers pinned)
- **Confirm-before-run:** early idea was "suggest + confirm + run" for everything;
  final model is: **raw commands run directly; AI-generated commands (`/ask`,
  `/debug`) show first and you press Enter.**
- **Auto-retry loop → `/debug`:** early idea was a silent loop that retries until
  it passes; final model is **user-triggered `/debug`, one attempt per press, no
  loop.**
- **Save nothing → save only the folder:** early idea (D15) was pure "terminal
  tab" — nothing kept on exit. Refined: the **history** is still discarded, but
  the **current folder is persisted** so navigation isn't wasted (D48). Not all
  state is equal — the folder is worth keeping; the command history isn't.

## Still open (to decide before/while building)
1. **`/start` vs auto-start** — does launching `ask` start the session
   automatically, or must you type `/start`? (Leaning: explicit `/start`.)
2. **Risk-scoring mechanism** — does the AI assign the risk level itself, or does
   a rule-list in our code, or both? (Leaning: AI assigns + a safety rule-list as
   backup.)
3. **Exact tunables** — history window (default 5), output trim size (default
   ~30 lines): confirm the starting numbers.
4. **Which folder wins on relaunch** — if you launch `ask` from a different
   folder than the saved one, does the **saved** folder win (resume) or the
   **launch** folder win? (Leaning: launch folder wins if you start somewhere
   explicitly, else resume the saved one.)
