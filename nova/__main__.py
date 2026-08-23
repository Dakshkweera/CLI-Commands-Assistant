"""
nova/__main__.py

The entry point of our tool. Running `python -m nova` runs this file.

For now this is just the "heartbeat": show a prompt, read what the user types,
decide what KIND of input it is (the dispatcher), and print what it WOULD do.
Raw commands now actually run (via the executor box). AI comes next.
"""

# os lets us read and work with folder paths.
# JS twins: process.cwd() and the `path` module.
import os

# Reads OUR OWN installed version — the number from pyproject.toml, looked up via
# the installed package metadata. stdlib (Python 3.8+). This way /version always
# matches what's actually installed; we never hardcode the number twice.
from importlib.metadata import version as pkg_version, PackageNotFoundError

# Import the executor box so we can actually run commands.
# The leading dot means "from this same package (nova/)".
# JS twin: import { runCommand } from "./executor".
from .executor import run_command

# Import the provider box so we can ask Gemini for commands.
from .provider import generate_command

# Import the memory box — the session notebook that records every command.
from .memory import Memory

# Import the storage box — saves the folder we end in, for the shell wrapper.
from .storage import save_last_folder

# Import the startup check — verifies the API key is set.
from .config import check_config

# rich gives us colored terminal output. One shared Console for the whole app.
from rich.console import Console

# prompt_toolkit powers the input line: a live dropdown menu of /commands and
# ↑-arrow history. It replaces the plain input() we used before.
# - PromptSession: one long-lived reader that remembers history for the session.
# - Completer/Completion: how we tell it what to suggest (the /command menu).
# - FormattedText: a colored prompt string (list of (style, text) pieces).
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings

console = Console()

# Icon + color for each risk level, so the danger is obvious at a glance.
RISK_STYLES = {
    "low": ("🟢", "green"),
    "medium": ("🟡", "yellow"),
    "high": ("🔴", "red"),
}

# Color of the "nova" name in the prompt. This is prompt_toolkit's style syntax
# (its own, NOT rich's): "fg:magenta" = magenta text. Same magenta as before.
PROMPT_STYLE = "bold fg:magenta"

# The slash-commands nova knows, each with a one-line description shown in the
# dropdown menu. Add a command here and it appears in the menu automatically.
COMMANDS = {
    "/ask": "generate a command from plain English",
    "/debug": "fix the last failed command",
    "/version": "show nova's version",
    "/exit": "quit nova",
}


def nova_version():
    """Return nova's installed version string (read from pyproject.toml's
    metadata, so it's never hardcoded in two places)."""
    try:
        return pkg_version("nova")
    except PackageNotFoundError:
        # Only happens if running from source without `pip install -e .`.
        return "unknown (run: pip install -e .)"


class SlashCompleter(Completer):
    """Builds the dropdown menu that appears as you type a leading `/`.

    prompt_toolkit calls get_completions() on every keystroke. We only suggest
    slash-commands, and only for the FIRST word — once you've typed the command
    and a space (e.g. `/ask `), we stop suggesting so your request text is free.
    """

    def get_completions(self, document, complete_event):
        # The text typed so far, up to the cursor (JS: like inputEl.value).
        text = document.text_before_cursor
        # Not a slash-command (or already past it) → suggest nothing.
        if " " in text or not text.startswith("/"):
            return
        # Offer every command whose name starts with what's typed. Typing "/"
        # matches them all; typing "/a" narrows to "/ask".
        for name, description in COMMANDS.items():
            if name.startswith(text):
                yield Completion(
                    # Insert the name PLUS a trailing space, so after you pick
                    # "/ask" the cursor sits ready for your request. (We .strip()
                    # input later, so the extra space never hurts a bare command.)
                    name + " ",
                    # Replace what the user has typed so far with the full name.
                    start_position=-len(text),
                    # Show just "/ask" in the menu (not the trailing space)...
                    display=name,
                    # ...and a greyed-out hint next to each menu item.
                    display_meta=description,
                )


def build_key_bindings():
    """Custom keypresses for the input line.

    Right now there's one: make Enter ACCEPT the highlighted menu item (and
    close the menu) instead of submitting the line. So when the dropdown is
    open, pressing Enter on "/ask" fills it in and lets you keep typing your
    request — a second Enter (menu closed) then submits.
    """
    bindings = KeyBindings()

    # @bindings.add("enter") registers this function as the handler for Enter.
    # (A decorator — like Express's app.get("/path", handler), but for a key.)
    @bindings.add("enter")
    def _(event):
        buffer = event.current_buffer          # the text being edited
        state = buffer.complete_state          # the menu state, or None if closed
        if state is not None:
            # Menu is open: take the highlighted item, or the first one if none
            # is highlighted yet, and insert it — WITHOUT submitting the line.
            completion = state.current_completion
            if completion is None and state.completions:
                completion = state.completions[0]
            if completion is not None:
                buffer.apply_completion(completion)
                return
        # Menu closed (or empty) → normal Enter: submit the line.
        buffer.validate_and_handle()

    return bindings


def run_and_record(command, memory, current_folder):
    """Run a command, show its output, and record the turn in the notebook.

    We use this in TWO places (raw commands and /ask), so putting it here keeps
    us from repeating the same run-print-record code twice (DRY).
    """
    result = run_command(command, cwd=current_folder)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    # Save what happened so /debug and /ask context can use it later.
    memory.record(command, result.stdout, result.stderr, result.returncode)
    return result


def change_folder(current_folder, command):
    """Handle a `cd ...` command by returning the NEW folder to track.

    Used for BOTH user-typed `cd` and AI-suggested `cd`, so a folder change is
    tracked no matter who wrote the command. Returns the new folder if it
    exists; otherwise prints an error and returns the folder unchanged.
    """
    # Everything after "cd" is the target path.
    target = command[2:].strip()
    # Strip surrounding quotes — the AI (correctly) quotes paths that contain
    # spaces, e.g. cd "Road to AI Engineer". We need the bare path without them.
    target = target.strip("\"'")
    # Build an absolute path relative to where we are now (handles "..", etc.).
    new_folder = os.path.abspath(os.path.join(current_folder, target))
    if os.path.isdir(new_folder):
        return new_folder
    print(f"cd: no such folder: {target}")
    return current_folder


# Words that show up in the error when the problem is the NETWORK (offline,
# Wi-Fi down, DNS not resolving) rather than something wrong with our request.
_NETWORK_HINTS = (
    "getaddrinfo", "connection", "timed out", "timeout",
    "network", "failed to establish", "name or service", "temporary failure",
)


def _looks_like_network_error(error):
    """True if this exception looks like a connectivity problem, not a real bug."""
    text = str(error).lower()
    return any(hint in text for hint in _NETWORK_HINTS)


def suggest_and_run(request, memory, current_folder):
    """Ask the AI for a command, show it + its risk, and run it on confirm.

    Shared by /ask and /debug — both do the same show-confirm-run dance, so we
    write it once here (DRY).
    """
    # Ask Gemini, giving it recent history for context. Wrap in try/except so a
    # failed network call prints an error but does NOT crash the session.
    # We return current_folder so the caller can update its variable — the AI's
    # command might be a `cd`, which changes the folder.
    try:
        suggestion = generate_command(request, memory.format_recent())
    except Exception as error:
        # A dropped connection shouldn't look like a scary crash. If it's a
        # network problem, say so in plain words; otherwise show the real error.
        if _looks_like_network_error(error):
            print("🌐 Can't reach the AI — check your internet connection and try again.")
        else:
            print(f"AI call failed: {error}")
        return current_folder

    # suggestion is a dict: {"command", "explanation", "risk"}.
    command = suggestion["command"]
    explanation = suggestion["explanation"]
    risk = suggestion["risk"]

    # Show the suggested command, what it does, and how risky it is — in color.
    # markup=False / highlight=False print the command and explanation literally,
    # so brackets in a command aren't mistaken for rich formatting codes.
    icon, color = RISK_STYLES.get(risk, ("•", "white"))
    console.print()
    console.print(f"  {command}", style="bold cyan", markup=False, highlight=False)
    console.print(f"  ↳ {explanation}", style="dim", markup=False, highlight=False)
    console.print(f"  risk: {icon} [{color}]{risk}[/{color}]")
    console.print()

    # Safety gate: nothing AI-written runs until you confirm (Enter / y / yes).
    confirm = input("Run it? [Enter/y = yes, anything else = no] ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("Skipped.")
        return current_folder

    # If the AI's command is a folder change, route it through our folder
    # tracking (same as a user-typed cd) so the prompt actually moves.
    if command == "cd" or command.startswith("cd "):
        return change_folder(current_folder, command)

    # Otherwise it's a normal command: run + record it. Folder is unchanged.
    run_and_record(command, memory, current_folder)
    return current_folder


def main():
    # Fail fast with a friendly message if the API key isn't set, instead of a
    # confusing crash later when we first try to call Gemini.
    check_config()

    # Our OWN memory of the current folder. We track it ourselves because each
    # command runs in a fresh helper that forgets it.
    # Start in the folder the terminal is CURRENTLY in (where you launched from).
    # os.getcwd() = "get current working directory" (JS: process.cwd()).
    current_folder = os.getcwd()

    # Create the session notebook. It records every command we run this session
    # so /debug can look back at what failed. Empty now, fills as we go.
    memory = Memory()

    # The input reader. Created ONCE (outside the loop) so it remembers your
    # command history for the whole session — press ↑ to recall past lines.
    # completer = our /command menu; complete_while_typing = show it live as you
    # type (that's what makes the menu pop up the instant you press "/").
    session = PromptSession(
        completer=SlashCompleter(),
        complete_while_typing=True,
        key_bindings=build_key_bindings(),
    )

    # The main loop. `while True:` runs forever until we `break` out of it.
    while True:

        # Build the colored prompt: "nova" in magenta, then the folder plainly.
        # FormattedText is a list of (style, text) pieces — the first is styled
        # with PROMPT_STYLE, the second ("") uses the default terminal color.
        prompt_message = FormattedText([
            (PROMPT_STYLE, "nova"),
            ("", f" {current_folder}> "),
        ])

        # Read one line. prompt_toolkit draws the prompt, the live /menu, and
        # handles ↑-history and line editing for us.
        # - Ctrl+C (KeyboardInterrupt): cancel THIS line, keep the session going.
        # - Ctrl+D (EOFError): treat like /exit — a normal way to quit a CLI.
        try:
            user_input = session.prompt(prompt_message).strip()
        except KeyboardInterrupt:
            continue
        except EOFError:
            save_last_folder(current_folder)
            print("bye!")
            break

        # ---- The dispatcher: decide what kind of input this is ----

        if user_input == "/exit":
            # Write the folder we ended in, so the shell wrapper can cd the real
            # terminal here after we quit (a program can't cd its parent itself).
            save_last_folder(current_folder)
            print("bye!")
            break

        elif user_input == "":
            # Empty line (they just pressed Enter). Skip and loop again.
            # `continue` jumps straight to the next loop pass (same as JS).
            continue

        elif user_input == "/ask" or user_input.startswith("/ask "):
            # A request for the AI. Everything after "/ask" is the question
            # ([5:] is safe even for bare "/ask" — it just gives "").
            question = user_input[5:].strip()
            if not question:
                # Bare "/ask" with no request — tell them what to do instead of
                # running "/ask" as a shell command.
                print("Type your request after /ask, e.g.  /ask list files bigger than 100MB")
                continue
            current_folder = suggest_and_run(question, memory, current_folder)

        elif user_input == "/debug" or user_input.startswith("/debug "):
            # Optional extra context, e.g. "/debug it's a node project".
            # [6:] is everything after "/debug"; strip() cleans spaces.
            hint = user_input[6:].strip()

            # Find the most recent FAILED command to fix (from the notebook).
            failure = memory.last_failure()
            if failure is None:
                print("Nothing to debug — no failed command yet.")
                continue

            # Build a "fix this" request from the failed command + its error.
            request = (
                f"The command `{failure['command']}` failed with this error:\n"
                f"{failure['error']}\n"
                "Give a corrected command for the same goal."
            )
            # If the user added a hint, include it to steer the AI.
            if hint:
                request += f"\nExtra context from the user: {hint}"

            # Same helper as /ask: get a suggestion (with history), show it,
            # and run it on confirm. Returns the (possibly changed) folder.
            current_folder = suggest_and_run(request, memory, current_folder)

        elif user_input == "/version":
            # Report nova's OWN version, straight from the installed package —
            # no shell command needed (and none exists for our tool anyway).
            print(f"nova {nova_version()}")

        elif user_input == "cd" or user_input.startswith("cd "):
            # `cd` is SPECIAL: it changes the folder, and that change must
            # persist. We intercept it and update our folder variable via the
            # shared change_folder helper (no subprocess needed).
            current_folder = change_folder(current_folder, user_input)

        elif user_input.startswith("/"):
            # A leading slash means "a nova command" — but this isn't one we
            # know. Guard it so a typo like /aks never runs as a shell command
            # (which is what caused that "not recognized" PowerShell error).
            print(f"Unknown command: {user_input.split()[0]}.  Type / to see the menu.")

        else:
            # Anything else is a raw command. Run it (in our tracked folder),
            # show its output, and record it in the notebook — all via the helper.
            run_and_record(user_input, memory, current_folder)


# The standard Python entry point.
# When this file is run directly (python -m nova), Python sets the hidden
# variable __name__ to "__main__", so this calls main(). If the file were
# imported by another file instead, __name__ would be its module name and
# main() would NOT auto-run.
if __name__ == "__main__":
    main()
