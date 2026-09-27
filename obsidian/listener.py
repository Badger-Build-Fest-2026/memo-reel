import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

CONN_STRING = os.getenv("DATABRICKS_DATABASE_URL")

# sys.executable is whatever Python (venv or system) is running this listener,
# and the app path is resolved relative to this file, so no machine-specific
# absolute paths are baked in.
PYTHON = sys.executable
APP = str(Path(__file__).resolve().parent / "script.py")

CHANNEL = "reel_capture_insert"

USER_ID = "9041096b-abec-4d51-8d80-7d37a969be4f"

# Run this once against the Lakebase Postgres database so INSERTs on
# capture_knowledge notify this listener. Payload is "capture_id:user_id" so
# the listener can filter to just USER_ID.
#
# CREATE OR REPLACE FUNCTION notify_reel_capture_insert()
# RETURNS trigger AS $$
# BEGIN
#     PERFORM pg_notify('reel_capture_insert', NEW.capture_id::text || ':' || NEW.user_id::text);
#     RETURN NEW;
# END;
# $$ LANGUAGE plpgsql;
#
# CREATE TRIGGER reel_capture_insert_trigger
# AFTER INSERT ON capture_knowledge
# FOR EACH ROW
# EXECUTE FUNCTION notify_reel_capture_insert();


def process_capture(capture_id: str) -> None:
    print(f"\nNew reel capture detected: {capture_id}")
    print("Running script.py...")

    try:
        result = subprocess.run(
            [
                PYTHON,
                APP,
                "--user-id",
                USER_ID,
                "--id",
                capture_id,
            ],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode == 0:
            print(f"Successfully processed: {capture_id}")
        else:
            print(f"script.py failed for: {capture_id}")

            if result.stderr:
                print(result.stderr)

    except Exception as e:
        print(f"Failed to launch script.py: {e}")


def main() -> None:
    if not CONN_STRING:
        raise RuntimeError("LAKEBASE_POSTGRES_CONN_STRING is not set.")

    if not USER_ID:
        raise RuntimeError("LAKEBASE_USER_ID is not set.")

    print("Connecting to Lakebase PostgreSQL...")

    with psycopg.connect(CONN_STRING, autocommit=True) as conn:
        conn.execute(f"LISTEN {CHANNEL}")

        print(f"Listening on PostgreSQL channel: {CHANNEL}")
        print("Waiting for new reel captures (INSERT events)...")
        print("Press Ctrl+C to stop.\n")

        for notification in conn.notifies():
            payload = notification.payload

            if not payload:
                print("Received notification without a capture ID.")
                continue

            capture_id, _, user_id = payload.partition(":")

            if not capture_id:
                print("Received notification without a capture ID.")
                continue

            if user_id != USER_ID:
                print(f"Skipping capture {capture_id} for other user: {user_id}")
                continue

            process_capture(capture_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nListener stopped.")