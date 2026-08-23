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

## Install

Requires **Python 3.10+** on **Windows** (with PowerShell). One command:

```powershell
pip install git+https://github.com/YOUR-USERNAME/nova.git
```

> Prefer isolated CLI installs? Use [`pipx`](https://pipx.pypa.io):
> `pipx install git+https://github.com/YOUR-USERNAME/nova.git`

That installs nova + its dependencies and creates a `nova` command.

## First run — your API key

Just run it:

```powershell
nova
```

On first run nova asks you to paste your **Gemini API key** (get one free at
https://aistudio.google.com/apikey), then saves it to `~/.nova/credentials` so
you're never asked again. If the key is later rejected or expired, nova lets you
paste a new one on the spot.

Two other ways to provide the key, if you prefer:
- **Environment variable:** `setx GEMINI_API_KEY "your-key"` (then reopen the terminal)
- **`.env` file:** copy `.env.example` to `.env` and fill in your key

## Optional: folder-follow shortcut

A program can't change the folder of the terminal that launched it, so to have
the real terminal "land" in the folder you navigated to inside nova, add this
function to your PowerShell profile (`notepad $PROFILE`):

```powershell
function nova {
    # Call the installed nova.exe explicitly (not this function) to avoid recursion.
    $exe = (Get-Command nova -CommandType Application -ErrorAction SilentlyContinue).Source
    if (-not $exe) { Write-Host "nova isn't on PATH."; return }
    & $exe
    if ($LASTEXITCODE -eq 0) {
        $dir = Get-Content "$HOME\.nova_last_folder" -ErrorAction SilentlyContinue
        if ($dir -and (Test-Path $dir)) { Set-Location $dir }
    }
}
```

Reload once with `. $PROFILE` (or open a new terminal).

## Develop / contribute

To work on nova from source (an editable install — changes apply on the next run):

```powershell
git clone https://github.com/YOUR-USERNAME/nova.git
cd nova
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

Put your key in a `.env` at the project root (or use any method above), then run
`python -m nova`.
