# Product Specification — `nova`

## 1. The problem

People know **what** they want to do in the terminal but not the **exact
command or syntax**. So they stop, leave the terminal, search the web, and copy
something that may not fit their OS/shell. When a command fails with a cryptic
error, they repeat the same dance. That context-switch — leaving the terminal to
figure out the terminal — is the pain.

## 2. The solution (one sentence)

> You describe the task in plain English; `nova` writes the command and shows it,
> you run it, and if it fails, `/debug` helps you fix it — all without leaving
> the terminal.

The user reads the real command output themselves. `nova` does not interpret or
explain results; its job is to help you reach a **working command**.

## 3. Who it's for

Anyone at a terminal — beginner to expert, frequent or occasional user. No
assumption of shell fluency.

## 4. Features

| ID | Feature | What it gives the user |
|----|---------|------------------------|
| F1 | Natural-language → command | Type intent in English, get a real command for this OS/shell |
| F2 | Human-in-the-loop run | The AI shows the command; **you press Enter** to run it |
| F3 | Risk Score | AI-generated commands are rated 🟢/🟡/🔴 by damage potential, shown before running |
| F4 | `/debug` fixing | On failure, the AI writes a corrected command using the last command + error + recent history |
| F5 | Steerable debug | `/debug <text>` lets you add context if the AI guesses wrong |
| F6 | Session memory | Every command (yours and the AI's) is recorded for the session |
| F7 | Environment awareness | The AI is told it's on Windows/PowerShell so commands actually work |

## 5. The command grammar

Default behaviour is a **normal shell**. The AI only wakes up on a `/` command.

| You type          | Treated as   | What happens                                               |
|-------------------|--------------|------------------------------------------------------------|
| `<any command>`   | raw command  | run as-is, record the result (no AI, no risk score)        |
| `cd <path>`       | folder change| intercepted — updates the tracked folder (no subprocess)   |
| `/ask <english>`  | request      | AI generates a command → show it + risk score → Enter runs |
| `/debug [text]`   | fix request  | AI uses last command + error + history → show fix → Enter runs |
| `/exit`           | control      | end the session; memory is discarded, exit folder is saved |

Only `/ask` and `/debug` call the API. Everything else is free.

The session **auto-starts** when you launch `nova` (no `/start` command) and
begins in the terminal's current folder.

## 6. The two AI flows

### `/ask` — generate a command
```
you: /ask list files bigger than 100MB
nova: Get-ChildItem -Recurse | Where-Object { $_.Length -gt 100MB }
     Risk: 🟢 Low (read-only)
     [Enter to run]
```

### `/debug` — fix the last failure
```
you: npm run buld          (typo — fails: "Unknown command: buld")
you: /debug
nova: npm run build
     Risk: 🟢 Low
     [Enter to run]
```
`nova` grabs the failed command + its error + recent history from memory
**automatically** — no copy-paste. Add your own hint with `/debug it's a Node
project`.

## 7. Success / failure

A command's success is judged by its **exit code**: `0` means it worked,
anything else means it failed. This is the same signal the shell itself uses.

## 8. Retry model — no loops

There is **no automatic retry loop**. Fixing is user-triggered: you type
`/debug` for one fix attempt, press Enter to run it, and if it's still wrong you
type `/debug` again. The human is in command at every step.

## 9. Non-goals (scope discipline)

- ❌ Not a general chatbot — terminal tasks only.
- ❌ Not an explainer — it does not narrate results; you read them.
- ❌ Not an autonomous agent — it never runs a chain of commands on its own.
- ❌ Not portable yet — targets Windows + PowerShell first.
- ❌ No unsupervised destruction — nothing AI-written runs without your Enter.
- ❌ No advanced context tricks yet — no summarization, no RAG.
