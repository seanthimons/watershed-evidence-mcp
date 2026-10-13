import httpx
import pytest

from watershed_evidence_mcp.http import JsonHttpClient, UpstreamServiceError


@pytest.mark.asyncio
async def test_http_failure_is_actionable_and_does_not_expose_transport_trace() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    client = JsonHttpClient(transport=transport)

    with pytest.raises(UpstreamServiceError, match="HTTP 503"):
        await client.get_json("https://example.test/unavailable")


@pytest.mark.asyncio
async def test_wrong_content_type_fails_safely() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html>error</html>",
            request=request,
        )
    )
    client = JsonHttpClient(transport=transport)

    with pytest.raises(UpstreamServiceError, match="content type"):
        await client.get_text("https://example.test/results", expected_content_types=("text/csv",))


@pytest.mark.asyncio
async def test_vendor_geojson_content_type_is_accepted() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/vnd.geo+json"},
            json={"features": []},
            request=request,
        )
    )
    client = JsonHttpClient(transport=transport)

    assert await client.get_json("https://example.test/summary") == {"features": []}


@pytest.mark.asyncio
async def test_oversized_response_fails_safely() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/csv"},
            content=b"a,b\n1,2\n",
            request=request,
        )
    )
    client = JsonHttpClient(max_response_bytes=4, transport=transport)

    with pytest.raises(UpstreamServiceError, match="safety limit"):
        await client.get_text("https://example.test/results", expected_content_types=("text/csv",))


@pytest.mark.asyncio
async def test_timeout_is_actionable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow upstream", request=request)

    client = JsonHttpClient(timeout_seconds=2, transport=httpx.MockTransport(timeout))

    with pytest.raises(UpstreamServiceError, match="timed out after 2 seconds"):
        await client.get_json("https://example.test/summary")
