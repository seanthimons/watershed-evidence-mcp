import pytest

from watershed_evidence_mcp.adapters.freshwater import FreshwaterAdapter
from watershed_evidence_mcp.models import BoundingBox


@pytest.mark.asyncio
async def test_freshwater_predicted_conductivity_cap_is_bounded() -> None:
    adapter = FreshwaterAdapter()
    with pytest.raises(ValueError, match="between 1 and 1000"):
        await adapter.predicted_conductivity(
            BoundingBox(west=-84.1, south=39.1, east=-84.0, north=39.2), 1001
        )
