import httpx
import pytest

from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.http import JsonHttpClient
from watershed_evidence_mcp.models import BoundingBox


@pytest.mark.asyncio
async def test_freshwater_predicted_conductivity_cap_is_bounded() -> None:
    adapter = FreshwaterAdapter()
    with pytest.raises(ValueError, match="between 1 and 1000"):
        await adapter.predicted_conductivity(
            BoundingBox(west=-84.1, south=39.1, east=-84.0, north=39.2), 1001
        )


def _adapter(payload: dict) -> FreshwaterAdapter:
    return FreshwaterAdapter(
        JsonHttpClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        )
    )


BOX = BoundingBox(west=-84.1, south=39.1, east=-84.0, north=39.2)


def _features(n: int) -> list[dict]:
    return [{"attributes": {"COMID": i}} for i in range(n)]


@pytest.mark.asyncio
async def test_exactly_at_cap_is_not_truncated() -> None:
    records, _, truncated = await _adapter({"features": _features(3)}).predicted_conductivity(
        BOX, 3
    )
    assert len(records) == 3
    assert truncated is False


@pytest.mark.asyncio
async def test_extra_row_marks_truncated_and_is_trimmed() -> None:
    records, _, truncated = await _adapter({"features": _features(4)}).predicted_conductivity(
        BOX, 3
    )
    assert len(records) == 3
    assert truncated is True


@pytest.mark.asyncio
async def test_exceeded_transfer_limit_marks_truncated() -> None:
    payload = {"features": _features(2), "exceededTransferLimit": True}
    _, _, truncated = await _adapter(payload).predicted_conductivity(BOX, 3)
    assert truncated is True
