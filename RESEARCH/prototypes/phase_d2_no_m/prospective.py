from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_ml.d2_no_m_prospective import append_prediction_batch, initialize_repaired_stream, record_missed_session, score_pinned_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the frozen three-cell D2-NM prediction-only stream")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register-repaired")
    register.add_argument("--reason", required=True)
    publish = commands.add_parser("publish-batch")
    publish.add_argument("--score-package", type=Path, required=True)
    publish.add_argument("--batch-id", required=True)
    missed = commands.add_parser("record-missed")
    missed.add_argument("--decision-session", required=True)
    missed.add_argument("--reason", required=True)
    score = commands.add_parser("score-pinned")
    score.add_argument("--package-dir", type=Path, required=True)
    score.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register-repaired":
        path = initialize_repaired_stream(reason=args.reason)
    elif args.command == "publish-batch":
        path = append_prediction_batch(args.score_package, batch_id=args.batch_id)
    elif args.command == "record-missed":
        path = record_missed_session(decision_session=args.decision_session, reason=args.reason)
    else:
        path = score_pinned_package(args.package_dir, output_dir=args.output_dir)
    print(json.dumps({"status": "PASS", "path": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
