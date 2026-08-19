# ask — a self-correcting terminal command assistant

`ask` is an interactive terminal assistant. You describe what you want in plain
English, it writes the command; when something fails, it helps you fix it — and
you stay in control the whole time.

> You know **what** you want to do in the terminal but not the exact **command**.
> Instead of leaving to search the web, you ask `ask`.

## What it does (in one picture)

```
You type intent  ->  ask writes a command  ->  you press Enter  ->  it runs
Something failed? ->  /debug  ->  ask writes a fix  ->  you press Enter  ->  it runs
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
| `/ask <english>`    | AI writes a command → shows it + risk score → Enter runs |
| `/debug [text]`     | AI fixes the last failure → shows it → Enter runs        |
| `/start`            | Begin a session (fresh history; resumes your last folder) |
| `/exit`             | End the session (history discarded; last folder is kept)  |

## Tech stack

- **Python 3.13** (sync, no web framework, no async needed)
- **Gemini API** (`google-genai` SDK), model **Flash**
- `python-dotenv` for the API key, `rich` for colored output
- `subprocess` (stdlib) to run commands

See [`docs/`](docs) for the full specification:

- [`docs/SPEC.md`](docs/SPEC.md) — the product: problem, features, flows, scope
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the boxes, data flow, context design
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — every decision we've locked in

## Status

Design phase complete. Building next, one "box" at a time.

## Setup (for when we start building)

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install google-genai python-dotenv rich
```

Put your Gemini API key (from https://aistudio.google.com/apikey) in a `.env`
file:

```
GEMINI_API_KEY=your-key-here
```
