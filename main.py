"""
AML IntelliGent Platform — Entry Point
=======================================
Run this file to start the interactive KYC analysis session.

Requirements:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY="sk-ant-..."

Usage:
    python main.py
"""

import os
import sys
import anthropic

from kyc_platform.super_agent import run as run_super_agent


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it with:  export ANTHROPIC_API_KEY='sk-ant-...'\n",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    run_super_agent(client)


if __name__ == "__main__":
    main()
