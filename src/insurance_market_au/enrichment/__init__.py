"""Research-only, pinned M2 insurance feature enrichment."""
from .provider import EnrichmentProvider, EnrichmentSpec, enrich_batch

__all__ = ["EnrichmentProvider", "EnrichmentSpec", "enrich_batch"]
