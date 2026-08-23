# Architecture — `nova`

## Guiding principle: separation of concerns

Each part of the app has **one job** and **one reason to change**. The whole
point is: *when you change how one thing works, the change stays in one place.*
This is what turns a script into a system — not complexity, but tidiness.

## The boxes

The app is a small set of independent "boxes" (modules), each with a single
responsibility.

| Box | Its one job | Would change when… |
|-----|-------------|--------------------|
| **Session** | The main loop: read input, decide (raw / `/ask` / `/debug` / `/exit`), record the turn | You add a new `/` command |
| **Memory** | Store every turn; build the small "note" of context for the AI | You change how much history to keep/send |
| **AI / Provider** | Talk to Gemini: generate a command, generate a fix, assign a risk score | You switch AI provider |
| **Executor** | Run a command, capture its output + exit code | You change how/where commands run |
| **Storage** | On exit, write the folder we ended in (for the shell wrapper) | You change how folder hand-off works |
| **Config** | Hold the API key, model name, and settings (history size, etc.) | You change how settings load |

### Dependency direction

The **Session (and CLI) depends on the other boxes; the other boxes do not
depend on the Session.** The AI and Executor boxes know nothing about `input()`
or `print()`. This keeps them testable and swappable.

## Data flow

```
                 ┌──────── Config (key, model, settings) ────────┐
                 │                                                ▼
 your input ─► Session ─► (decide what kind of input) ─► AI/Provider ─► command + risk
                 │                                                │
                 │                                                ▼
                 │                                     Executor (run → output, exit code)
                 │                                                │
                 └──────────────► Memory ◄────────────────────────┘
                          (record every turn; build the note)
```

## The core data type: a "Turn"

Instead of passing loose values around, the app uses one clean shape — a
**Turn** — recorded after every command:

```
Turn = {
  command:    the exact command that ran
  output:     its stdout (trimmed if very long)
  error:      its stderr (if any)
  exit_code:  0 = success, non-zero = failure
}
```

Memory is just an ordered list of Turns for the current session.

## The Memory box in detail

Memory has three small jobs (three methods on the `Memory` class):

- `record(command, output, error, exit_code)` — save a Turn. Called after
  **every** command, raw or AI-generated.
- `format_recent(n=5)` — build the small context "note" (a short text summary of
  the last *n* turns) to send the AI.
- `last_failure()` — find the most recent failed Turn, used by `/debug`.

### What is a "note"?

The AI has **no memory** — it forgets everything after each reply. So before any
AI call, we send it a short catch-up "note" (this is the *context*). Managing
context = deciding what goes in that note so it stays small but useful.

### Context rules (kept deliberately simple and cheap)

Recording is free (it's just RAM). Sending costs tokens, so notes stay small:

1. **Keep the last ~5 commands** (a tunable window). Older ones are dropped from
   the note.
2. **Trim long output** (~first/last 30 lines) so one noisy command can't bloat
   a note.
3. **`/ask` note** = environment (OS/shell) + your request. Little/no history.
4. **`/debug` note** = environment + the failed command + its error + the last
   few commands.

All of this lives **inside the Memory box**. The rest of the app just asks for a
note; it never builds one itself. Change the rules → change only this box.

> **Note on the two AI flows:** both `/ask` and `/debug` call **one** Provider
> function — `generate_command(request, history)`. `/debug` simply builds its
> `request` from the last failed command + its error before calling it. One
> function, one JSON shape, used by both.

## Memory lifecycle (like a terminal tab)

- The **history** lives **only in RAM**, only for the session. Not written to disk.
- Launching `nova` **auto-starts** the session with fresh, empty history (there is
  no `/start` command). It begins in the terminal's **current** folder.
- Every turn (raw or AI) is recorded automatically.
- **`/exit`** → the session ends, the history reference is released, Python frees
  it (reference counting), and the process exits. The history is gone.
- **Exception:** the folder you ended in is written to a small file so the shell
  wrapper can move the **real terminal** there after exit. See "State handling".
- Capacity is effectively unlimited in RAM (text is tiny). The real limit is how
  much we *send* to the AI — which the context rules above control.

## State handling — why `cd` needs special care

### The problem
Each command runs in a **fresh, disposable helper process** (like Node's
`child_process`). A child process gets a *copy* of the parent's state and its
changes never flow back up ("state flows down, never up" — pass-by-value). So a
`cd` in one helper is lost the moment that helper dies, and the next helper
starts fresh. In a real terminal this works because **one shell stays alive** and
handles `cd` itself; our naive model spawns a new shell per command.

### The insight
Most commands are **independent** (`ls`, `git status`, `python x.py`) — losing
them costs nothing. But the **current folder** (`cd`) is *state* that affects
every later command. Not all state is equal: the folder is worth tracking; the
command history is not.

### The solution (Solution B — track state ourselves)
1. Our program holds a `current_folder` variable.
2. Normal commands run in a fresh helper, told where to start via the **`cwd`**
   parameter (`subprocess.run(cmd, cwd=current_folder)` — same as Node's
   `exec(cmd, { cwd })`).
3. `cd` is **intercepted**: no helper is spawned; we just update the variable.
4. The prompt is built from the variable (`nova C:\project\sub>`), so it always
   shows the right folder.
5. On `/exit`, we write **only** the folder (one line to a small file,
   `~/.nova_last_folder`). A small **PowerShell wrapper function** reads that file
   after `nova` exits and `cd`s the **real terminal** into it — so you "land" in
   the folder you navigated to. (A program can't change its parent shell's
   folder itself; the wrapper does it from the outside.)

The tracking lives in the **CLI + Storage** boxes; the wrapper lives in your
PowerShell profile. Fuller state (environment variables, etc.) would need a
single long-lived shell (Solution A) — deferred as a later "real tool" upgrade.
For now, only the folder is handled.

### Why PowerShell only
Commands run through `powershell -Command`, and the folder-follow wrapper is a
PowerShell function. So `nova` targets **Windows + PowerShell**. cmd and Git Bash
can run the core tool (`python -m nova`) but get no `nova` shortcut and no
folder-follow; Mac/Linux would need the executor + commands adapted.

## Packaging — run from any folder
`python -m nova` only works when Python can find the `nova` package. We make it
findable everywhere by installing the project as an **editable package**
(`pip install -e .`, described by `pyproject.toml`) — the same idea as
`npm link`. After that, the wrapper calls the venv's Python by absolute path, so
`nova` works from any folder without activating the venv first.

## The Risk Score

AI-generated commands (`/ask`, `/debug`) are rated before you run them. Raw
commands you type yourself are **not** rated (you wrote them, you own them).

| Level | Damage scope | Examples |
|-------|--------------|----------|
| 🟢 Low | harmless / read-only | `--version`, `Get-ChildItem`, `Test-Path` |
| 🟡 Medium | affects this **project/folder** | deletes or edits files here |
| 🔴 High | affects the **system** | system-wide delete, format, config changes |

The rating is judged from **the command text only** — not from history. This
keeps it simple and cheap.

## Tech stack

| Concern | Choice | Node.js equivalent (for reference) |
|---------|--------|-------------------------------------|
| Language | Python 3.10+ (developed on 3.13, sync) | Node.js |
| Install packages | `pip` into a **venv** | `npm` into `node_modules` |
| Package/build config | `pyproject.toml` (`pip install -e .`) | `package.json` (`npm link`) |
| Gemini SDK | `google-genai` | `@google/genai` |
| Model | `gemini-3.6-flash` | — |
| Load `.env` secrets | `python-dotenv` | `dotenv` |
| Terminal colors | `rich` | `chalk` |
| Run commands | `subprocess` → PowerShell (stdlib) | `child_process` |
| Read input | `input()` (stdlib) | `readline` |

### Why no web framework and no async

- **No FastAPI/Express:** `nova` is a **CLI**, not a web server. There are no HTTP
  requests to handle, so no web framework is needed.
- **No async:** the tool does one thing at a time (read → wait for AI → run →
  repeat) for a single user. Async only helps with *many concurrent* operations.
  Simple sync Python is both easier and correct here. (Async will be a separate
  learning side-quest later.)

An SDK is just a package that wraps the raw HTTP API behind clean function
calls — the same way `mongoose` wraps MongoDB or the `stripe` package wraps
Stripe. `google-genai` wraps Gemini's REST API so we call functions instead of
hand-writing HTTP.
