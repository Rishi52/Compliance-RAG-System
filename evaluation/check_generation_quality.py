from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "generation_benchmark_dev_results.json"
)

DEFAULT_THRESHOLDS = {
    "retrieval_hit_rate": 0.95,
    "context_hit_rate": 0.80,
    "answer_rate": 0.80,
    "citation_valid_rate": 0.80,
    "expected_source_hit_rate": 0.80,
    "mean_citation_coverage": 0.90,
}


def load_report(path: Path) -> dict[str, Any]:
    """Load a generation benchmark JSON report."""

    if not path.exists():
        raise FileNotFoundError(
            f"Generation report was not found at: {path}"
        )

    report = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(report, dict):
        raise ValueError(
            "Generation report must be a JSON object."
        )

    return report


def get_quality_summary(
    report: dict[str, Any],
) -> dict[str, Any]:
    """Return generation quality metrics."""

    summary = report.get("summary")

    if not isinstance(summary, dict):
        raise ValueError(
            "Generation report is missing its summary."
        )

    quality = summary.get("quality")

    if not isinstance(quality, dict):
        raise ValueError(
            "Generation report is missing quality metrics."
        )

    return quality


def find_quality_failures(
    quality: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> list[str]:
    """Return metrics that fall below frozen thresholds."""

    threshold_values = (
        DEFAULT_THRESHOLDS
        if thresholds is None
        else thresholds
    )

    failures: list[str] = []

    for metric, minimum in threshold_values.items():
        metric_value = quality.get(metric)

        if not isinstance(metric_value, (int, float)):
            raise ValueError(
                f"Quality summary is missing metric: {metric}"
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
            "Check generation quality against frozen thresholds."
        )
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    report = load_report(arguments.report)
    quality = get_quality_summary(report)
    failures = find_quality_failures(quality)

    for metric, minimum in DEFAULT_THRESHOLDS.items():
        actual = float(quality[metric])

        print(
            f"{metric}: {actual:.3f} "
            f"(minimum {minimum:.3f})"
        )

    if failures:
        print("Generation quality gate failed:")

        for failure in failures:
            print(f"- {failure}")

        raise SystemExit(1)

    print("Generation quality gate passed.")


if __name__ == "__main__":
    main()