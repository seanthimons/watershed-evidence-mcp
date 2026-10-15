from datetime import date, datetime

import pytest

from watershed_evidence_mcp.adapters.wqp import WqpAdapter, _encode_token
from watershed_evidence_mcp.cache import DuckDbCache
from watershed_evidence_mcp.models import QueryScope, WqpQuery

HEADER = "MonitoringLocationIdentifier,CharacteristicName,ActivityStartDate,ResultMeasureValue\n"


class DatedClient:
    """Serves one row per listed date, honoring the date window and resultLimit."""

    def __init__(self, dates: list[date]) -> None:
        self.dates = dates
        self.requests = 0

    async def get_text(self, url, params, **kwargs) -> str:
        self.requests += 1
        fmt = "%m-%d-%Y"
        lo = datetime.strptime(params["startDateLo"], fmt).date()
        hi = datetime.strptime(params["startDateHi"], fmt).date()
        hits = [d for d in self.dates if lo <= d <= hi][: int(params["resultLimit"])]
        return HEADER + "".join(f"USGS-1,Specific conductance,{d},1\n" for d in hits)


def make(dates: list[date], tmp_path, limit: int, end: date = date(2024, 1, 8)):
    query = WqpQuery(
        scope=QueryScope(station_ids=["USGS-1"]),
        characteristic_names=["Specific conductance"],
        start_date=date(2024, 1, 1),
        end_date=end,
        result_limit=limit,
    )
    client = DatedClient(dates)
    return query, client, WqpAdapter(client=client, cache=DuckDbCache(tmp_path / "c.duckdb"))


async def collect(adapter: WqpAdapter, query: WqpQuery) -> list:
    pages, token = [], None
    for _ in range(50):
        page = await adapter.collection_page(query, token)
        pages.append(page)
        token = page.continuation_token
        if token is None:
            return pages
    raise AssertionError("pagination did not terminate")


@pytest.mark.asyncio
async def test_multi_page_collection_tiles_range_and_returns_every_record(tmp_path) -> None:
    dates = [date(2024, 1, d) for d in (1, 2, 3, 4, 5, 6, 7, 8)]
    query, _, adapter = make(dates, tmp_path, limit=3)

    pages = await collect(adapter, query)

    assert len(pages) > 1
    assert pages[0].window_start == query.start_date
    assert pages[-1].window_end == query.end_date
    for prev, nxt in zip(pages, pages[1:], strict=False):
        assert (nxt.window_start - prev.window_end).days == 1
    got = [r["activity_date"] for p in pages for r in p.result.records]
    assert got == [d.isoformat() for d in dates]
    assert all(not p.result.truncated for p in pages)


@pytest.mark.asyncio
async def test_small_collection_is_one_final_page(tmp_path) -> None:
    query, _, adapter = make([date(2024, 1, 2)], tmp_path, limit=10)
    page = await adapter.collection_page(query)
    assert page.continuation_token is None
    assert len(page.result.records) == 1


@pytest.mark.asyncio
async def test_single_day_over_cap_raises_instead_of_dropping_records(tmp_path) -> None:
    query, _, adapter = make([date(2024, 1, 2)] * 5, tmp_path, limit=3)
    with pytest.raises(ValueError, match="cannot be split further"):
        await collect(adapter, query)


@pytest.mark.asyncio
async def test_invalid_continuation_tokens_are_rejected(tmp_path) -> None:
    query, _, adapter = make([], tmp_path, limit=3)
    other, _, _ = make([], tmp_path, limit=4)
    from watershed_evidence_mcp.adapters.wqp import query_id

    for token in (
        "not-a-token",
        _encode_token("deadbeef", date(2024, 1, 2), 2),
        _encode_token(query_id(query), date(2025, 1, 1), 2),
        _encode_token(query_id(other), date(2024, 1, 2), 2),
    ):
        with pytest.raises(ValueError, match="continuation token"):
            await adapter.collection_page(query, token)
