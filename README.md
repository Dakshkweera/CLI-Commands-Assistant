# nova — a self-correcting terminal command assistant

`nova` is an interactive terminal assistant. You describe what you want in plain
English, it writes the command; when something fails, it helps you fix it — and
you stay in control the whole time.

> You know **what** you want to do in the terminal but not the exact **command**.
> Instead of leaving to search the web, you ask `nova`.

## What it does (in one picture)

```
You type intent  ->  nova writes a command  ->  you press Enter  ->  it runs
Something failed? ->  /debug  ->  nova writes a fix  ->  you press Enter  ->  it runs
```

You read the real command output yourself. The tool does **not** explain
results — it helps you get to a working command.

## Core ideas

- **It's a session** you work inside, like a terminal tab. Close it and its
  memory is gone.
- **Default = a normal shell.** Anything you type just runs.
- **`/` commands call the AI** — `/ask` to generate a command, `/debug` to fix
  the last failure.
- **You press Enter to run** anything the AI writes. Nothing AI-generated runs
  on its own.
- **AI-generated commands show a Risk Score** (🟢/🟡/🔴) so you know how
  dangerous a command is before you run it.

## Commands

| You type            | What happens                                              |
|---------------------|----------------------------------------------------------|
| `<any command>`     | Runs as a raw command (no AI, no risk score)             |
| `cd <path>`         | Changes the tracked folder (intercepted, not run in a subprocess) |
| `/ask <english>`    | AI writes a command → shows it + risk score → Enter runs |
| `/debug [text]`     | AI fixes the last failure → shows it → Enter runs        |
| `/version`          | Print nova's own version                                  |
| `/exit`             | End the session (history discarded; the terminal lands in the folder you navigated to) |

The session **auto-starts** when you launch `nova` — there is no `/start`. It
begins in whatever folder your terminal is currently in. **Type `/`** for a live
dropdown of commands, and press **↑** to recall earlier commands.

## Tech stack

- **Python 3.10+** (sync, no web framework, no async needed)
- **Gemini API** (`google-genai` SDK), model **`gemini-3.6-flash`**
- `prompt_toolkit` for the input line (command dropdown + history)
- `python-dotenv` for the API key, `rich` for colored output
- `subprocess` (stdlib) to run commands (via PowerShell)

See [`docs/`](docs) for the full specification:

- [`docs/SPEC.md`](docs/SPEC.md) — the product: problem, features, flows, scope
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the boxes, data flow, context design
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — every decision we've locked in

## Status

**Working.** All core features are built: raw commands, `cd` tracking (yours and
the AI's), `/ask`, `/debug` (with history + optional hint), `/version`, a live
`/command` dropdown with ↑-history, in-RAM session memory, colored risk scores,
friendly network-error handling, folder-follow-on-exit, and a `pip`-installable
package that runs from any folder.

> **Runs on Windows + PowerShell.** Commands are executed through PowerShell, and
> the `nova` shortcut (with folder-follow) is a PowerShell function. It does not
> run in cmd, Git Bash, or on Mac/Linux without changes.

## Setup

```powershell
# 1. Create + activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install the project as an editable package (so `python -m nova` works anywhere)
pip install -e .
```

Put your Gemini API key (from https://aistudio.google.com/apikey) in a `.env`
file at the project root:

```
GEMINI_API_KEY=your-key-here
```

### The `nova` shortcut (folder-follow)

A program can't change the folder of the terminal that launched it, so to have
the real terminal "land" in the folder you navigated to inside `nova`, add this
function to your PowerShell profile (`notepad $PROFILE`):

```powershell
function nova {
    & "C:\path\to\CLI AI Assistant\venv\Scripts\python.exe" -m nova
    if ($LASTEXITCODE -eq 0) {
        $dir = Get-Content "$HOME\.nova_last_folder" -ErrorAction SilentlyContinue
        if ($dir -and (Test-Path $dir)) { Set-Location $dir }
    }
}
```

Reload the profile once with `. $PROFILE` (or open a new terminal). Now just
type `nova` from any PowerShell terminal.
