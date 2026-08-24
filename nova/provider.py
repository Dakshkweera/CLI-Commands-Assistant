"""
nova/provider.py

The Provider box. Its one job: talk to Gemini.

Given a plain-English request, it asks Gemini for ONE shell command, a short
explanation, and a risk level — and returns them as plain data (a dict).

It does NOT run anything and does NOT print anything. It just calls the AI and
returns the result. (Boxes return data; the CLI does the I/O.)
"""

import json
import logging
import platform

from google import genai
from google.genai import types

from .config import get_api_key, MODEL

# The SDK logs a harmless "automatic function calling (AFC)" notice on every
# call. Silence it so our output stays clean.
logging.getLogger("google_genai").setLevel(logging.ERROR)

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
        # get_api_key() is read HERE (not at import) so a key entered during
        # first-run setup is picked up before the first AI call.
        _client = genai.Client(api_key=get_api_key())
    return _client


def reset_client():
    """Drop the cached client so the next call rebuilds it with a fresh key.
    Used after the user enters a NEW key (e.g. the old one was rejected), so the
    new key actually takes effect instead of reusing the old client."""
    global _client
    _client = None


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
        "\n"
        "HOW THIS TOOL RUNS YOUR COMMAND (so it actually works):\n"
        "- Each command runs in a FRESH PowerShell process starting in the "
        "user's current folder. Only the folder carries over between commands "
        "(the tool tracks it) — do NOT rely on variables, aliases, or env vars "
        "set by an earlier command.\n"
        "- Give ONE complete, self-contained, NON-interactive command (use flags "
        "like -y/--yes); the tool captures output and cannot answer prompts.\n"
        "- For paths, use paths relative to the current folder, or `~` for the "
        "home folder (supported, e.g. `cd ~\\Desktop`). Do NOT use $HOME, "
        "$env:USERPROFILE, %USERPROFILE%, or `cd -` — the tool doesn't support "
        "those.\n"
        "- To change directory, ALWAYS use `cd <path>` (never Set-Location) so "
        "the tool can track the folder; you may chain more commands after it "
        'with `;`, e.g. `cd ~\\Docs; explorer .`.\n'
        "\n"
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
            # temperature 0 = always pick the most likely command (max
            # determinism): same request → same command, far fewer surprises.
            temperature=0,
        ),
    )

    # response.text is the JSON string Gemini returned; json.loads turns that
    # string into a real Python dict we can read with ["command"] etc.
    return json.loads(response.text)
