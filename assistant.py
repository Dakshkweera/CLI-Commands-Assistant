"""
Stage 1: A minimal CLI assistant that talks to the Gemini API.

Goal: prove the whole pipe works end to end —
    you type  ->  Python  ->  Gemini  ->  Python  ->  terminal
Nothing fancy yet. We harden it in later stages.
"""

import os
import sys

from google import genai


def main() -> None:
    # 1. Read the API key from the environment (never hardcode secrets).
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.", file=sys.stderr)
        print("Get a key at https://aistudio.google.com/apikey", file=sys.stderr)
        sys.exit(1)

    # 2. Create the client. This is our door to the Gemini API.
    client = genai.Client(api_key=api_key)

    print("CLI Assistant (Stage 1). Type 'exit' or Ctrl+C to quit.\n")

    # 3. The REPL: Read a line, Eval via Gemini, Print, Loop.
    while True:
        user_input = input("you > ").strip()

        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue  # ignore empty lines

        # 4. Send the message to the model and get a reply.
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_input,
        )

        # 5. Show the model's text back to the user.
        print(f"ai  > {response.text}\n")


if __name__ == "__main__":
    main()
