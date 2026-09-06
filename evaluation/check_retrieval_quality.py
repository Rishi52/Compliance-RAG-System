from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "retrieval_benchmark_dev_results.json"
)

DEFAULT_METHOD = "hybrid_reranked"

DEFAULT_THRESHOLDS = {
    "recall@1": 0.80,
    "recall@3": 0.95,
    "mrr@5": 0.90,
    "ndcg@5": 0.90,
}


def load_report(path: Path) -> dict[str, Any]:
    """Load a retrieval benchmark JSON report."""

    if not path.exists():
        raise FileNotFoundError(
            f"Retrieval report was not found at: {path}"
        )

    report = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(report, dict):
        raise ValueError(
            "Retrieval report must be a JSON object."
        )

    return report


def get_method_summary(
    report: dict[str, Any],
    method: str,
) -> dict[str, Any]:
    """Return summary metrics for one retrieval method."""

    summary = report.get("summary")

    if not isinstance(summary, dict):
        raise ValueError(
            "Retrieval report is missing its summary."
        )

    method_summary = summary.get(method)

    if not isinstance(method_summary, dict):
        raise ValueError(
            f"Retrieval report has no method: {method}"
        )

    return method_summary


def find_quality_failures(
    method_summary: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> list[str]:
    """Return descriptions of metrics below their thresholds."""

    threshold_values = (
        DEFAULT_THRESHOLDS
        if thresholds is None
        else thresholds
    )

    failures: list[str] = []

    for metric, minimum in threshold_values.items():
        metric_value = method_summary.get(metric)

        if not isinstance(metric_value, (int, float)):
            raise ValueError(
                f"Method summary is missing metric: {metric}"
            )

        actual = float(metric_value)

        if actual < minimum:
            failures.append(
                f"{metric}: expected >= {minimum:.3f}, "
                f"found {actual:.3f}"
            )

    return failures


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check a retrieval report against quality "
            "thresholds."
        )
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
    )
    parser.add_argument(
        "--method",
        default=DEFAULT_METHOD,
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    report = load_report(arguments.report)
    method_summary = get_method_summary(
        report,
        arguments.method,
    )
    failures = find_quality_failures(method_summary)

    print(f"Method: {arguments.method}")

    for metric, minimum in DEFAULT_THRESHOLDS.items():
        actual = float(method_summary[metric])

        print(
            f"{metric}: {actual:.3f} "
            f"(minimum {minimum:.3f})"
        )

    if failures:
        print("Retrieval quality gate failed:")

        for failure in failures:
            print(f"- {failure}")

        raise SystemExit(1)

    print("Retrieval quality gate passed.")


if __name__ == "__main__":
    main()