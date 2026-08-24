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

# Import the provider box so we can ask Gemini for commands. reset_client lets
# us rebuild the AI client after the user swaps in a new API key.
from .provider import generate_command, reset_client

# Import the memory box — the session notebook that records every command.
from .memory import Memory

# Import the storage box — saves the folder we end in (for the shell wrapper)
# and the API key (so the user enters it only once).
from .storage import save_last_folder, save_api_key

# Import the key resolver — finds the API key (env / .env / saved file).
from .config import get_api_key

# rich gives us colored terminal output. One shared Console for the whole app.
from rich.console import Console

# prompt_toolkit powers the input line: a live dropdown menu of /commands and
# ↑-arrow history. It replaces the plain input() we used before.
# - PromptSession: one long-lived reader that remembers history for the session.
# - Completer/Completion: how we tell it what to suggest (the /command menu).
# - FormattedText: a colored prompt string (list of (style, text) pieces).
from prompt_toolkit import PromptSession, prompt
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


def _split_leading_cd(command):
    """Split a compound command into its leading `cd` part and the rest.

    e.g. 'cd "System design"; explorer .'  ->  ('cd "System design"', 'explorer .')
         'cd Docs && dir'                   ->  ('cd Docs', 'dir')
         'cd Docs'                          ->  ('cd Docs', '')   (nothing after)

    We scan for the first `;` or `&&` that is OUTSIDE quotes, so a separator
    inside a quoted path (rare) isn't mistaken for the split point.
    """
    in_quote = None                       # which quote char we're inside, or None
    i = 0
    while i < len(command):
        ch = command[i]
        if in_quote:                      # inside quotes: only look for the closer
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):            # entering a quoted section
            in_quote = ch
        elif ch == ";":                   # top-level ';' → split here
            return command[:i].strip(), command[i + 1:].strip()
        elif ch == "&" and command[i:i + 2] == "&&":   # top-level '&&' → split
            return command[:i].strip(), command[i + 2:].strip()
        i += 1
    return command.strip(), ""            # no separator: it's all the cd part


def _resolve_cd(current_folder, cd_command):
    """Work out the folder a `cd` command points to.

    Returns (folder, ok, error): the new folder, whether it exists, and an error
    message (or None). Does NOT print — the caller prints/records so a failed cd
    can be remembered for /debug.
    """
    # Everything after "cd" is the target path; strip surrounding quotes so a
    # spaced path like cd "Road to AI Engineer" resolves to the bare path.
    target = cd_command[2:].strip().strip("\"'")
    # Expand a leading ~ to the user's home folder (C:\Users\You). os.path.join
    # doesn't know about ~, so without this it'd look for a folder named "~".
    target = os.path.expanduser(target)
    if not target:                        # bare "cd" — nowhere to go, no-op
        return current_folder, True, None
    # Build an absolute path relative to where we are now (handles "..", etc.).
    # If target is already absolute (e.g. an expanded ~), join returns it as-is.
    new_folder = os.path.abspath(os.path.join(current_folder, target))
    if os.path.isdir(new_folder):
        return new_folder, True, None
    return current_folder, False, f"cd: no such folder: {target}"


def run_cd_command(command, memory, current_folder):
    """Handle any command that starts with `cd` — including a COMPOUND one like
    `cd "System design"; explorer .`.

    We peel off the leading `cd` (updating our tracked folder), then run whatever
    remains IN that new folder. Used for both user-typed and AI-suggested cd, so
    a folder change is tracked no matter who wrote it.
    """
    cd_part, rest = _split_leading_cd(command)
    new_folder, ok, error = _resolve_cd(current_folder, cd_part)
    if not ok:
        # cd failed: show the error AND record it (exit code 1) so /debug can
        # look back and offer a fix. Don't run the rest in the wrong folder.
        print(error)
        memory.record(command, "", error, 1)
        return current_folder
    if rest:
        # Run the remaining command(s) in the folder we just moved to.
        run_and_record(rest, memory, new_folder)
    return new_folder


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


# Words that mean the API KEY itself was rejected (wrong / expired / unauthorized).
_BAD_KEY_HINTS = (
    "api key not valid", "api_key_invalid", "invalid api key",
    "api key expired", "key expired", "permission denied",
    "permission_denied", "unauthenticated",
)

# Words that mean we hit the rate limit / free-tier QUOTA (not a bad key).
_QUOTA_HINTS = ("resource_exhausted", "exhausted", "quota", "rate limit", "too many requests")


def _looks_like_bad_key(error):
    """True if the API key was rejected (invalid / expired / unauthorized)."""
    text = str(error).lower()
    if any(hint in text for hint in _BAD_KEY_HINTS):
        return True
    # google-genai errors carry the HTTP status in .code; 401/403 = auth problem.
    return getattr(error, "code", None) in (401, 403)


def _looks_like_quota(error):
    """True if we hit the rate limit / free-tier quota."""
    text = str(error).lower()
    if any(hint in text for hint in _QUOTA_HINTS):
        return True
    return getattr(error, "code", None) == 429


def _prompt_and_save_key(label):
    """Ask for an API key (masked), save it, and make it active immediately.

    Shared by first-run setup and the "your key was rejected" recovery flow.
    Returns the key, or None if the user entered nothing.
    """
    key = prompt(f"  {label}: ", is_password=True).strip()
    if not key:
        return None
    save_api_key(key)                    # remember it for next time
    os.environ["GEMINI_API_KEY"] = key   # use it right now, this session
    reset_client()                       # rebuild the AI client with the new key
    return key


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
        # Turn scary raw errors into plain-language help. Order matters:
        # check the specific causes first, fall back to the raw error last.
        if _looks_like_network_error(error):
            print("🌐 Can't reach the AI — check your internet connection and try again.")
        elif _looks_like_bad_key(error):
            # The key is wrong/expired — let them fix it right here, no restart.
            print("🔑 Your API key was rejected (invalid or expired).")
            if _prompt_and_save_key("Paste a new Gemini API key") is not None:
                print("✓ Saved. Run your command again.")
        elif _looks_like_quota(error):
            # A rate limit isn't a bad key — a new key from the SAME account
            # won't help, so we say so instead of asking them to re-enter it.
            print("⏳ You've hit the Gemini free-tier limit for now.")
            print("   A new key from the SAME Google account won't help — the limit is per account.")
            print("   Wait a bit and try again, or paste a key from a DIFFERENT account (Enter to skip):")
            if _prompt_and_save_key("New key") is not None:
                print("✓ Saved. Run your command again.")
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

    # If the AI's command is (or starts with) a folder change, route it through
    # our cd handler so the prompt moves — and any chained command (e.g.
    # `cd "X"; explorer .`) runs in the new folder.
    if command == "cd" or command.startswith("cd "):
        return run_cd_command(command, memory, current_folder)

    # Otherwise it's a normal command: run + record it. Folder is unchanged.
    run_and_record(command, memory, current_folder)
    return current_folder


def ensure_api_key():
    """Make sure we have a Gemini API key.

    On first run (no key found anywhere) this asks the user to paste one and
    saves it to ~/.nova/credentials, so they never have to enter it again.
    """
    if get_api_key():
        return  # already have one (env var, .env, or the saved file)

    # First run — welcome the user and ask for their key.
    console.print("\nWelcome to nova! 🌟", style="bold magenta")
    console.print(
        "Paste your Gemini API key to get started "
        "(free at https://aistudio.google.com/apikey):",
        style="dim",
    )
    # Shared helper prompts (masked), saves, and activates the key.
    if _prompt_and_save_key("key>") is None:
        raise SystemExit("No key entered — run nova again when you have one.")
    console.print("✓ Saved to ~/.nova/credentials. You're all set.\n", style="green")


def main():
    # Make sure we have an API key. On first run this prompts for one and saves
    # it, so the user is never dropped into a confusing crash later.
    ensure_api_key()

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
            # persist. We intercept it (a plain cd runs no subprocess); a
            # compound cd like `cd X; dir` also runs its tail in the new folder.
            current_folder = run_cd_command(user_input, memory, current_folder)

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
