import json
from datetime import UTC, datetime

import pytest

from watershed_evidence_mcp.evaluation import _measure, report_payload, write_reports


@pytest.mark.asyncio
async def test_measure_records_bounded_live_request_metadata_without_payload() -> None:
    async def bounded_request() -> int:
        return 3

    result = await _measure(
        "representative request",
        "example public endpoint",
        {"result_limit": 25},
        bounded_request,
    )

    assert result.outcome == "success"
    assert result.record_count == 3
    assert result.query_shape == {"result_limit": 25}
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_measure_reports_upstream_failure_without_traceback_or_payload() -> None:
    async def failing_request() -> int:
        raise RuntimeError("upstream response: <large raw payload>\ntraceback detail")

    result = await _measure("failing request", "example endpoint", {}, failing_request)

    assert result.outcome == "error"
    assert result.record_count is None
    assert result.detail == "upstream response: <large raw payload>"


def test_reports_are_dated_machine_and_human_readable_metadata_only(tmp_path) -> None:
    ran_at = datetime(2026, 10, 13, 14, 30, tzinfo=UTC)
    from watershed_evidence_mcp.evaluation import EvaluationResult

    result = EvaluationResult(
        scenario="WQP bounded measurements",
        endpoint="Water Quality Portal Result/search",
        query_shape={"result_limit": 25},
        outcome="success",
        record_count=25,
        duration_ms=123,
    )
    payload = report_payload(ran_at, [result])
    json_path, markdown_path = write_reports(tmp_path, ran_at, [result])

    assert json_path.name == "live-evaluation-20261013T143000Z.json"
    assert markdown_path.name == "live-evaluation-20261013T143000Z.md"
    saved = json.loads(json_path.read_text())
    assert saved["ran_at"] == "2026-10-13T14:30:00+00:00"
    assert saved["results"][0]["record_count"] == 25
    markdown = markdown_path.read_text()
    assert "WQP bounded measurements" in markdown
    assert "raw response bodies, credentials, and private URLs" in markdown
    assert "<large raw payload>" not in markdown
    assert payload["ran_at"] == "2026-10-13T14:30:00+00:00"
