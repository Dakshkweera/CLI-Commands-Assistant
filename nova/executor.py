"""
nova/executor.py

The Executor box. Its one job: RUN a shell command and report back what
happened — the output, any error, and whether it succeeded.

It does NOT print anything itself. It just runs the command and RETURNS the
result; main() decides what to show. (Boxes return data; the CLI does the I/O.)
"""

import subprocess


def run_command(command, cwd=None):
    """
    Run `command` in PowerShell and return the result.

    - command: the text to run, e.g. "python --version"
    - cwd: which folder to run in (None = the current folder). We'll use this
      later for the folder-tracking (`cd`) feature.

    The returned object has three useful fields:
    - .stdout      -> the normal output   (a string)
    - .stderr      -> the error output    (a string)
    - .returncode  -> 0 if it worked, non-zero if it failed
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,  # capture stdout/stderr instead of letting them print directly
        text=True,            # hand us back strings, not raw bytes
        cwd=cwd,              # run in this folder (None = current)
    )
    return result
