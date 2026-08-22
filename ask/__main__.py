"""
ask/__main__.py

The entry point of our tool. Running `python -m ask` runs this file.

For now this is just the "heartbeat": show a prompt, read what the user types,
decide what KIND of input it is (the dispatcher), and print what it WOULD do.
Raw commands now actually run (via the executor box). AI comes next.
"""

# os lets us read and work with folder paths.
# JS twins: process.cwd() and the `path` module.
import os

# Import the executor box so we can actually run commands.
# The leading dot means "from this same package (ask/)".
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
    # Build an absolute path relative to where we are now (handles "..", etc.).
    new_folder = os.path.abspath(os.path.join(current_folder, target))
    if os.path.isdir(new_folder):
        return new_folder
    print(f"cd: no such folder: {target}")
    return current_folder


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
        print(f"AI call failed: {error}")
        return current_folder

    # suggestion is a dict: {"command", "explanation", "risk"}.
    command = suggestion["command"]
    explanation = suggestion["explanation"]
    risk = suggestion["risk"]

    # Show the suggested command, what it does, and how risky it is.
    print(f"\n  {command}")
    print(f"  ↳ {explanation}")
    print(f"  risk: {risk}\n")

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

    # The main loop. `while True:` runs forever until we `break` out of it.
    while True:

        # Show the prompt WITH the current folder, then wait for a line.
        # The folder comes from our variable, so the prompt always shows where
        # we are. .strip() removes surrounding whitespace (like JS .trim()).
        user_input = input(f"ask {current_folder}> ").strip()

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

        elif user_input.startswith("/ask "):
            # A request for the AI. Slice off "/ask " to get the question,
            # then hand it to the shared suggest-and-run helper.
            question = user_input[5:]
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

        elif user_input == "cd" or user_input.startswith("cd "):
            # `cd` is SPECIAL: it changes the folder, and that change must
            # persist. We intercept it and update our folder variable via the
            # shared change_folder helper (no subprocess needed).
            current_folder = change_folder(current_folder, user_input)

        else:
            # Anything else is a raw command. Run it (in our tracked folder),
            # show its output, and record it in the notebook — all via the helper.
            run_and_record(user_input, memory, current_folder)


# The standard Python entry point.
# When this file is run directly (python -m ask), Python sets the hidden
# variable __name__ to "__main__", so this calls main(). If the file were
# imported by another file instead, __name__ would be its module name and
# main() would NOT auto-run.
if __name__ == "__main__":
    main()
