import argparse
import sys

from collegedata.db import connect
from collegedata.runner import REGISTRY, run_job


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="collegedata")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a pipeline job")
    run.add_argument("job_name")
    args = parser.parse_args(argv)

    if args.job_name not in REGISTRY:
        print(f"unknown job: {args.job_name}", file=sys.stderr)
        return 1

    with connect() as conn:
        result = run_job(REGISTRY[args.job_name](), conn)
        conn.commit()
    if result.status == "failed":
        print(result.error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
