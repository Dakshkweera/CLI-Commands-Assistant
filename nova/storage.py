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
