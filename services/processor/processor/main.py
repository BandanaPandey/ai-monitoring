from __future__ import annotations

import json
import sys
import time

from .config import Settings
from .job_runner import JobRunner


def main() -> int:
    settings = Settings.from_env()
    runner = JobRunner(
        mode=settings.mode,
        file_store_path=settings.file_store_path,
        aggregate_store_path=settings.aggregate_store_path,
    )
    command = sys.argv[1] if len(sys.argv) > 1 else "run-once"

    if command == "run-once":
        print(json.dumps(runner.run_once(), indent=2))
        return 0

    if command == "run-loop":
        while True:
            print(json.dumps(runner.run_once(), indent=2))
            time.sleep(settings.interval_seconds)

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
