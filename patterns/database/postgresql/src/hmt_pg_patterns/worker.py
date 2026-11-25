"""Run only as a fixed command under an authenticated, key-pinned Tailcat server."""

import argparse
import json
import sys
import time
from pathlib import Path

import psycopg

from .transport import require_tailcat_peer
from .worker_config import load_config
from .worker_io import IngressRequest, process_deadline, read_frame
from .worker_service import serve


def main() -> int:
    """Exit1 means rejected/uncertain; no failure path depends on a diagnostic pipe."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        require_tailcat_peer(config.binding())
        with process_deadline(config.deadline_seconds):
            raw = read_frame(sys.stdin.fileno(), 131072, time.monotonic() + config.deadline_seconds)
            request = IngressRequest.model_validate_json(raw)
            result = serve(config, request)
            print(json.dumps(result, sort_keys=True), flush=True)
    except (OSError, ValueError, RuntimeError, psycopg.Error, ExceptionGroup):
        # Library APIs retain their typed failures; the fixed child has a bounded exit contract.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
