"""Source caveats and the provenance block attached to every tool response."""

from __future__ import annotations

from watershed_evidence_mcp.models import Provenance

WQP_CAVEAT = (
    "WQP aggregates public records from many contributors. Preserve source identifiers, units, "
    "qualifiers, and method information; do not treat this retrieval as a regulatory determination."
)
WATERS_CAVEAT = (
    "A river name can match more than one feature. Candidates are not a complete river corridor; "
    "the caller must select a candidate and define an explicit query area."
)
ATTAINS_CAVEAT = (
    "ATTAINS reports assessment decisions for a reporting cycle. It does not establish the "
    "current condition of a waterbody or prove the cause of an observed condition."
)
FRESHWATER_CAVEAT = (
    "Explorer layers are curated/modelled screening context and may need local "
    "calibration. Do not represent them as current raw observations or a "
    "regulatory finding."
)
VOCAB_CAVEAT = (
    "Vocabulary results are the source of exact query values; do not silently "
    "substitute near matches."
)

CAVEATS = {
    "wqp": WQP_CAVEAT,
    "waters": WATERS_CAVEAT,
    "attains": ATTAINS_CAVEAT,
    "freshwater": FRESHWATER_CAVEAT,
    "vocabulary": VOCAB_CAVEAT,
}


def provenance(source: str, version: str, query_url: str, caveat: str) -> dict:
    return Provenance(
        source=source,
        source_version=version,
        query_url=query_url,
        caveat=caveat,
    ).model_dump(mode="json")
