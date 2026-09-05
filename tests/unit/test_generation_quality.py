import json
from pathlib import Path

import pytest

from evaluation.check_generation_quality import (
    find_quality_failures,
    get_quality_summary,
    load_report,
)


def test_load_report_reads_json_object(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.json"
    payload = {
        "summary": {
            "quality": {
                "answer_rate": 1.0,
            }
        }
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    assert load_report(path) == payload


def test_load_report_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="was not found",
    ):
        load_report(tmp_path / "missing.json")


def test_get_quality_summary_returns_metrics() -> None:
    quality = {
        "citation_valid_rate": 1.0,
    }

    report = {
        "summary": {
            "quality": quality,
        }
    }

    assert get_quality_summary(report) == quality


def test_quality_gate_detects_regression() -> None:
    failures = find_quality_failures(
        quality={
            "answer_rate": 0.50,
        },
        thresholds={
            "answer_rate": 0.80,
        },
    )

    assert failures == [
        "answer_rate: expected >= 0.800, "
        "found 0.500"
    ]


def test_quality_gate_rejects_missing_metric() -> None:
    with pytest.raises(
        ValueError,
        match="missing metric",
    ):
        find_quality_failures(
            quality={},
            thresholds={
                "answer_rate": 0.80,
            },
        )