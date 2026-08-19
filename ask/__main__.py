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


def main():
    # Our OWN memory of the current folder. We track it ourselves because each
    # command runs in a fresh helper that forgets it. os.getcwd() = "get current
    # working directory" — where we launched from (JS: process.cwd()).
    current_folder = os.getcwd()

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
            # Anything starting with "/ask " is a request for the AI.
            # user_input[5:] means "the string from index 5 onward" — it
            # slices off the "/ask " prefix. (Like JS user_input.slice(5).)
            question = user_input[5:]
            print(f"[would ask AI]: {question}")

        elif user_input == "/debug":
            # User wants to fix the last failed command.
            print("[would debug the last failure]")

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
            # Anything else is a raw command. Run it through the executor box,
            # telling it to run IN our tracked folder (cwd=current_folder).
            result = run_command(user_input, cwd=current_folder)

            # An empty string is "falsy" in Python, so `if result.stdout:`
            # means "if there was any output". end="" stops print from adding
            # an extra blank line (the captured output already ends in a newline).
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")


# The standard Python entry point.
# When this file is run directly (python -m ask), Python sets the hidden
# variable __name__ to "__main__", so this calls main(). If the file were
# imported by another file instead, __name__ would be its module name and
# main() would NOT auto-run.
if __name__ == "__main__":
    main()
