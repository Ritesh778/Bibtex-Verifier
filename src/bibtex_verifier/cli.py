import argparse
import asyncio
from pathlib import Path

from .service import VerificationService


async def run(
    input_path: Path,
    output_path: Path | None,
    fail_on_review: bool,
) -> int:
    service = VerificationService()

    try:
        bibtex = input_path.read_text(encoding="utf-8")

        report = await service.verify_bibtex(bibtex)
    finally:
        await service.close()

    payload = report.model_dump_json(indent=2)

    if output_path:
        output_path.write_text(
            payload + "\n",
            encoding="utf-8",
        )
    else:
        print(payload)

    blocking_statuses = {
        "needs_review",
        "unresolved",
        "conflict",
    }

    has_blocking_entry = any(entry.status.value in blocking_statuses for entry in report.entries)

    if fail_on_review and has_blocking_entry:
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Verify a BibTeX file against public scholarly metadata indexes.")
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to the BibTeX file.",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help=("Optional path for the JSON verification report."),
    )

    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help=("Return exit code 1 when an entry requires manual review."),
    )

    args = parser.parse_args()

    exit_code = asyncio.run(
        run(
            args.input,
            args.output,
            args.fail_on_review,
        )
    )

    raise SystemExit(exit_code)
