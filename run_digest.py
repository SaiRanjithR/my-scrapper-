#!/usr/bin/env python3
"""Standalone runner for the Antigravity Digest workflow.

This script directly executes the ADK workflow pipeline without needing
agents-cli, avoiding virtual-environment isolation issues on CI.
"""

import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import workflow


def main() -> int:
    print("=" * 60)
    print("ANTIGRAVITY DIGEST — Standalone Runner")
    print("=" * 60)

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(
        user_id="github-actions", app_name="antigravity-digest"
    )
    runner = Runner(
        agent=workflow,
        session_service=session_service,
        app_name="antigravity-digest",
    )

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="Trigger Daily Digest")],
    )

    print("Starting workflow execution...")
    final_output = None
    try:
        for event in runner.run(
            new_message=message,
            user_id="github-actions",
            session_id=session.id,
        ):
            # Capture the last non-None output from workflow nodes
            if event.output is not None:
                final_output = event.output
    except Exception as exc:
        print(f"\nFATAL: Workflow execution failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 60)
    print(f"WORKFLOW RESULT: {final_output}")
    print("=" * 60)

    if final_output and "successfully" in str(final_output).lower():
        return 0
    else:
        print("WARNING: Digest may not have been sent. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
