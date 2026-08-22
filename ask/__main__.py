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


def suggest_and_run(request, memory, current_folder):
    """Ask the AI for a command, show it + its risk, and run it on confirm.

    Shared by /ask and /debug — both do the same show-confirm-run dance, so we
    write it once here (DRY).
    """
    # Ask Gemini, giving it recent history for context. Wrap in try/except so a
    # failed network call prints an error but does NOT crash the session.
    try:
        suggestion = generate_command(request, memory.format_recent())
    except Exception as error:
        print(f"AI call failed: {error}")
        return

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
    if confirm in ("", "y", "yes"):
        run_and_record(command, memory, current_folder)
    else:
        print("Skipped.")


def main():
    # Our OWN memory of the current folder. We track it ourselves because each
    # command runs in a fresh helper that forgets it. os.getcwd() = "get current
    # working directory" — where we launched from (JS: process.cwd()).
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
            # User wants to quit: say bye and leave the loop.
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
            suggest_and_run(question, memory, current_folder)

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
            # and run it on confirm.
            suggest_and_run(request, memory, current_folder)

        elif user_input == "cd" or user_input.startswith("cd "):
            # `cd` is SPECIAL: it changes the folder, and that change must
            # persist across future commands. If we ran it in a fresh helper,
            # the change would die with that helper. So we intercept `cd` and
            # update our OWN folder variable instead of running it.

            # Grab whatever was typed after "cd" (everything from index 2 on).
            target = user_input[2:].strip()

            # Build the new absolute path relative to where we are now.
            # os.path.join glues them; os.path.abspath resolves ".." and cleans
            # it up. If `target` is already absolute, join returns it as-is.
            new_folder = os.path.abspath(os.path.join(current_folder, target))

            # Only switch if that folder really exists (like a real `cd` does).
            if os.path.isdir(new_folder):
                current_folder = new_folder
            else:
                print(f"cd: no such folder: {target}")

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
