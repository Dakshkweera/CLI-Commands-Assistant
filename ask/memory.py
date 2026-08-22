"""
ask/memory.py

The Memory box. It remembers what happened during this session: every command,
its output, its error, and whether it passed.

- /ask uses recent history for context (so follow-ups like "now delete it" work).
- /debug uses the last FAILED turn to write a fix.

Memory lives only in RAM — when the program ends, it's gone (like a terminal tab).
"""

# How many past turns to show the AI. Small = cheap + focused. (Tunable.)
HISTORY_SIZE = 5

# Cap how much output we keep per command, so one huge output can't bloat memory.
MAX_OUTPUT_LINES = 30


def _trim(text):
    """If output is very long, keep the first lines and drop the rest."""
    lines = text.splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return text
    kept = "\n".join(lines[:MAX_OUTPUT_LINES])
    return kept + "\n... (trimmed) ..."


class Memory:
    def __init__(self):
        # The list of turns for this session. Starts empty.
        # self.turns is like `this.turns` in a JS class.
        self.turns = []

    def record(self, command, output, error, exit_code):
        """Save one turn. Output/error are trimmed so memory stays small."""
        self.turns.append({
            "command": command,
            "output": _trim(output),
            "error": _trim(error),
            "exit_code": exit_code,
        })

    def last_failure(self):
        """Return the most recent FAILED turn, or None if there's no failure."""
        # reversed() walks the list newest-first; return the first fail we hit.
        for turn in reversed(self.turns):
            if turn["exit_code"] != 0:
                return turn
        return None

    def format_recent(self, n=HISTORY_SIZE):
        """Build a short text summary of the last n turns, for the AI note."""
        lines = []
        for turn in self.turns[-n:]:          # [-n:] = "the last n items"
            status = "ok" if turn["exit_code"] == 0 else "FAILED"
            lines.append(f"$ {turn['command']} -> {status}")
            if turn["exit_code"] != 0 and turn["error"]:
                lines.append(f"  error: {turn['error']}")
        return "\n".join(lines)
