# Decision Log — `nova`

The single source of truth. Every decision we've locked in, so the design stays
consistent as we build.

## What it is
| # | Decision |
|---|----------|
| D1 | A self-correcting terminal command assistant (working name `nova`) |
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
| D10 | The session **auto-starts** when you launch `nova` (no `/start`); `/exit` ends it |
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
| D47 | The prompt shows the tracked folder (e.g. `nova C:\project\sub>`), updated automatically because it's built from the variable |
| D48 | Every launch starts in the terminal's **current** folder. On `/exit`, we discard the history but **write the folder we ended in** (one line to `~/.nova_last_folder`) so a **PowerShell wrapper** can `cd` the **real terminal** there — you "land" in the folder you navigated to (a program can't move its parent shell itself) |
| D49 | Keeping one shell alive for full state (env vars, etc.) is a later "real tool" upgrade; for now only the **folder** is tracked |
| D50 | Distributed via a **`pip`-installable package** (`pyproject.toml` + `pip install -e .`) so `python -m nova` runs from any folder; the wrapper calls the venv's Python by absolute path |
| D51 | Targets **PowerShell** specifically: commands run via `powershell -Command`, and the `nova` shortcut is a PowerShell profile function (cmd/Git Bash/Mac/Linux not supported without changes) |

## Context (the "note" sent to the AI)
| # | Decision |
|---|----------|
| D20 | Send **small notes** to keep it cheap/fast |
| D21 | Keep only the **last ~5 commands** (a tunable number) |
| D22 | **Trim long output** (~30 lines) before it bloats a note |
| D23 | `/ask` note = environment + your request (little/no history) |
| D24 | `/debug` note = environment + failed command + error + last few commands |
| D25 | All note logic lives in **one Memory box**: `record()` saves a turn, `format_recent()` builds the note, `last_failure()` finds the turn to fix |

## Environment & tech
| # | Decision |
|---|----------|
| D26 | Targets **Windows + PowerShell first** (not portable yet) |
| D27 | The AI is always told the **environment** (OS/shell) so commands work here |
| D28 | Uses the **Gemini API**, model **`gemini-3.6-flash`** (free tier — good for a student) |
| D40 | Language is **Python** (3.10+, developed on 3.13; chosen to learn it for the AI-engineer path) |
| D41 | SDK is **`google-genai`**; secrets via **`python-dotenv`**; output via **`rich`**; commands via **`subprocess`** |
| D42 | **Simple sync Python** — no FastAPI (it's a CLI, not a web server) and no async (single-user, sequential) |

## Architecture principles
| # | Decision |
|---|----------|
| D29 | **Separation of concerns** — each job in its own box (Session, Memory, Executor, AI/Provider, Config) |
| D30 | Changes should **stay in one box** — the whole reason for the boxes |
| D31 | Goal: eventually **deploy it** and make it industry-standard |
| D43 | Session/CLI depends on the core boxes; core boxes do not depend on the CLI (keeps them testable/swappable) |

## Input & UX
| # | Decision |
|---|----------|
| D52 | The input line uses **`prompt_toolkit`** (not bare `input()`): a live `/command` dropdown built from the `COMMANDS` dict, plus **↑** history from one long-lived session |
| D53 | The dropdown menu is **data-driven** — add a command to `COMMANDS` and it appears automatically; the menu is never hardcoded |
| D54 | **Enter accepts** a highlighted menu item (and keeps editing) instead of submitting, so picking `/ask` lets you keep typing the request |
| D55 | **Guards** keep bad input off the shell: bare `/ask` prints a usage hint, and any unknown `/command` is caught with a message instead of being run raw |
| D56 | `/version` reports nova's own version, read from the **installed package metadata** (single source of truth = `pyproject.toml`, never hardcoded twice) |
| D57 | AI-call **network errors** are detected and shown as a friendly "can't reach the AI" line; genuine bugs still show their real error |

## API key & distribution
| # | Decision |
|---|----------|
| D58 | Key resolution order (first hit wins): **env var → `.env` → saved file** `~/.nova/credentials` |
| D59 | **First-run onboarding** — with no key, nova prompts for one (masked), saves it, and asks only once. I/O lives in the CLI layer; Config/Storage stay quiet |
| D60 | The Provider reads the key **at client-creation time**, not at import — so a key entered mid-session takes effect immediately |
| D61 | **Runtime key recovery** — a rejected/expired key triggers a re-prompt (`reset_client()` rebuilds the client); a quota limit is explained, not treated as a bad key |
| D62 | The key is stored **locally in plaintext** (like `~/.aws/credentials`) — acceptable for a personal key; `.env` stays git-ignored, `.env.example` ships only a placeholder |
| D63 | **Compound `cd`** (`cd "X"; explorer .`) is split (quote-aware): peel the leading `cd`, then run the rest in the new folder |
| D64 | Distributed as a **`pip`-installable package** with an **entry point** (`[project.scripts]`), so `pip install git+<repo>` gives a real `nova` command |

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
- **Save nothing → follow the folder out:** early idea (D15) was pure "terminal
  tab" — nothing kept on exit. Refined: the **history** is still discarded, but on
  exit we write the folder we ended in so a shell wrapper moves the **real
  terminal** there (D48). We do **not** resume it inside `nova` — each launch
  starts in the terminal's current folder. Not all state is equal: the folder is
  worth handing back to the shell; the command history isn't.
- **Two AI functions → one:** early plan had separate "generate" and "fix"
  paths. Final: a single `generate_command(request, history)` serves both; `/debug`
  just builds a "this failed, fix it" request first.
- **`gemini-2.5-flash` → `gemini-3.6-flash`:** a 404 ("not available to new keys")
  after a key regeneration forced the model bump — a one-line change in Config,
  which is exactly why settings live in one box (D41/D29).

## Resolved (were open during design, now settled by the code)
1. **`/start` vs auto-start → auto-start.** Launching `nova` starts the session
   automatically; there is no `/start` command (D10).
2. **Risk-scoring mechanism → the AI assigns it.** The model returns the level in
   its JSON; there is no separate rule-list yet (D36/D37). A backup rule-list
   stays a possible later addition.
3. **Exact tunables → confirmed.** History window `HISTORY_SIZE = 5`, output trim
   `MAX_OUTPUT_LINES = 30` (both in `memory.py`, easy to change).
4. **Which folder wins → the launch folder, always.** `nova` always starts in the
   terminal's current folder; the saved file is only for the wrapper to move the
   parent shell on exit, not to resume inside `nova` (D48).
