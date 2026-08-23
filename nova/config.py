"""
nova/config.py

The Config box. Its job: load all our settings in ONE place — the API key and
the model name — so the rest of the app reads them from here instead of
scattering environment lookups everywhere.
"""

import os

from dotenv import load_dotenv

from .storage import load_api_key

# Read the .env file and load its values into the environment.
# After this line, os.environ can see GEMINI_API_KEY from your .env.
# JS twin: require("dotenv").config().
load_dotenv()

# Which Gemini model to use. "flash" is fast and has a generous free tier.
# Google told us (via a 404) that new keys must use 3.6-flash, not 2.5-flash.
# It's just a string — swap it here if you ever want a different model.
MODEL = "gemini-3.6-flash"


def get_api_key():
    """Return the Gemini API key, or None if we don't have one yet.

    Looks in order (first hit wins):
      1. the GEMINI_API_KEY environment variable — also filled by a .env file;
         an explicit override for power users / CI.
      2. the key saved from nova's first-run setup (~/.nova/credentials).

    Returning None is normal on first run — the CLI then prompts for a key and
    saves it, so the next call finds it here.
    """
    return os.environ.get("GEMINI_API_KEY") or load_api_key()
