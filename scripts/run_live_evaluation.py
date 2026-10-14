#!/usr/bin/env python3
"""Run bounded live public-service evaluation and write dated metadata-only reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from watershed_evidence_mcp.evaluation import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation-reports"),
        help="Directory for dated JSON and Markdown reports (default: evaluation-reports).",
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    json_path, markdown_path = main(args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    run()
