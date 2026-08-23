"""
nova/config.py

The Config box. Its job: load all our settings in ONE place — the API key and
the model name — so the rest of the app reads them from here instead of
scattering environment lookups everywhere.
"""

import os

from dotenv import load_dotenv

# Read the .env file and load its values into the environment.
# After this line, os.environ can see GEMINI_API_KEY from your .env.
# JS twin: require("dotenv").config().
load_dotenv()

# The Gemini API key, read from the environment (which .env just populated).
# .get() returns None if it's missing (instead of crashing).
API_KEY = os.environ.get("GEMINI_API_KEY")

# Which Gemini model to use. "flash" is fast and has a generous free tier.
# Google told us (via a 404) that new keys must use 3.6-flash, not 2.5-flash.
# It's just a string — swap it here if you ever want a different model.
MODEL = "gemini-3.6-flash"


def check_config():
    """
    Make sure the API key is actually present. If not, stop the program with a
    friendly message instead of a confusing crash deep inside the SDK later.
    """
    if not API_KEY:
        raise SystemExit(
            "Error: GEMINI_API_KEY is not set.\n"
            "Add it to your .env file:  GEMINI_API_KEY=your-key-here\n"
            "Get a key at https://aistudio.google.com/apikey"
        )
