"""
nova/storage.py

The Storage box. On exit, it writes the folder we ended up in to a small file.

Why: a program CANNOT change the folder of the terminal that launched it
(a child process can't change its parent — "state flows down, never up"). So to
"exit into" the folder you navigated to, a tiny shell wrapper reads this file
after `nova` exits and cd's the real terminal there. This file is that hand-off.
"""

import os

# Where we write the folder we ended in — a hidden file in your HOME directory,
# so the shell wrapper always knows where to find it.
STATE_FILE = os.path.join(os.path.expanduser("~"), ".nova_last_folder")


def save_last_folder(folder):
    """Write the folder we ended in to the state file (called on /exit)."""
    try:
        # open(..., "w") = write mode; `with` auto-closes the file when done.
        with open(STATE_FILE, "w") as f:
            f.write(folder)
    except OSError:
        # If saving fails (permissions, etc.), it's not worth crashing over.
        pass


# Where we remember the user's Gemini API key so they enter it only once.
# A file inside a hidden ~/.nova folder (like ~/.aws/credentials). Plain text —
# fine for a personal key on your own machine (your user profile is private).
KEY_DIR = os.path.join(os.path.expanduser("~"), ".nova")
KEY_FILE = os.path.join(KEY_DIR, "credentials")


def load_api_key():
    """Return the saved API key, or None if the user hasn't set one yet."""
    try:
        with open(KEY_FILE) as f:
            # .strip() drops any stray newline/spaces; "" becomes None below.
            return f.read().strip() or None
    except OSError:
        # No file yet (first run) — that's expected, not an error.
        return None


def save_api_key(key):
    """Save the API key to ~/.nova/credentials, creating the folder if needed."""
    try:
        # exist_ok=True = don't error if the folder is already there (mkdir -p).
        os.makedirs(KEY_DIR, exist_ok=True)
        with open(KEY_FILE, "w") as f:
            f.write(key.strip())
    except OSError:
        pass
