"""
ask/provider.py

The Provider box. Its one job: talk to Gemini.

Given a plain-English request, it asks Gemini for ONE shell command, a short
explanation, and a risk level — and returns them as plain data (a dict).

It does NOT run anything and does NOT print anything. It just calls the AI and
returns the result. (Boxes return data; the CLI does the I/O.)
"""

import json
import platform

from google import genai
from google.genai import types

from .config import API_KEY, MODEL

# The Gemini client is created LAZILY — on first use, not at import time.
# Why: importing this module shouldn't need the key. That lets main() run
# config.check_config() first and give a friendly error if the key is missing.
_client = None


def get_client():
    """Return the Gemini client, creating it once on first use.

    `global _client` lets us update the module-level _client from inside this
    function (otherwise Python treats it as a new local variable).
    """
    global _client
    if _client is None:
        _client = genai.Client(api_key=API_KEY)
    return _client


def build_system_prompt():
    """
    The 'system prompt' tells Gemini who it is and what environment we're on,
    so its commands actually fit our shell. platform.system() returns "Windows".
    """
    return (
        f"You are a command-line assistant for {platform.system()} using the "
        "PowerShell shell.\n"
        "The user describes a task in plain English. Reply with ONE command "
        "that accomplishes it in PowerShell.\n"
        "To change directory, ALWAYS use `cd <path>` (never Set-Location), so "
        "the tool can track the folder.\n"
        "Also rate how dangerous the command is:\n"
        "  low    = read-only / harmless (e.g. --version, Get-*, ls)\n"
        "  medium = changes files in the current project/folder\n"
        "  high   = affects the whole system or deletes things irreversibly\n"
        'Respond ONLY as JSON: {"command": "...", "explanation": "...", '
        '"risk": "low|medium|high"}\n'
        "Do not use markdown or backticks."
    )


def generate_command(request, history=""):
    """
    Ask Gemini for a command. Used by BOTH /ask and /debug (one function).

    - request: what we want. For /ask it's the user's question ("list files");
      for /debug it's a "this command failed with X, fix it" message.
    - history: a short summary of recent commands (from memory.format_recent),
      so the AI has context. Optional — empty by default.

    Returns a dict like:
        {"command": "...", "explanation": "...", "risk": "low"}
    """
    # If we have recent history, put it BEFORE the request so the AI sees the
    # context (e.g. what folder we're in, what just failed).
    if history:
        contents = f"Recent commands:\n{history}\n\nRequest: {request}"
    else:
        contents = request

    response = get_client().models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(),
            # Force Gemini to return valid JSON instead of prose. Far more
            # reliable than trying to parse free text.
            response_mime_type="application/json",
        ),
    )

    # response.text is the JSON string Gemini returned; json.loads turns that
    # string into a real Python dict we can read with ["command"] etc.
    return json.loads(response.text)
