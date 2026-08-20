"""Container start: migrate, optionally seed, then serve."""

import os
import shutil
import subprocess
import sys


def main() -> None:
    # Do not use `python -m alembic`: this repo has an `alembic/` package
    # (migration scripts), which shadows the installed Alembic CLI.
    alembic = shutil.which("alembic")
    if alembic is None:
        raise RuntimeError("alembic CLI not found on PATH")
    subprocess.check_call([alembic, "upgrade", "head"])
    if os.getenv("SEED_SAMPLE_DATA", "true").lower() != "false":
        subprocess.check_call([sys.executable, "-m", "app.seed"])

    port = os.environ.get("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()
