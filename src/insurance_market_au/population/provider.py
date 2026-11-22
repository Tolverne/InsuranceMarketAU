"""M1.5 read-only population port for M2 enrichment, M3 segments and M4 models.

A consumer pins a release_id. It cannot discover or silently switch to
"latest". Every open checks content hashes, control totals, source lineage
and the declared physical schema. Batch iterators do not load the entire
synthetic fleet into application memory.
"""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
from typing import Iterable, Iterator, Mapping

from insurance_market_au.data_foundation.m1 import ROOT
from insurance_market_au.population.releases import (
    BASE_DIMS, CONTRACT, FILTER_DIMS, OUTPUT_FILES,
    verify_population,
)

FEATURE_VIEW = "market_vehicle_base_v1"
DEFAULT_COLUMNS = (
    "synthetic_row_id", "registered_state", "vehicle_type",
    "manufacture_year", "motive_power", "make", "model",
    "registered_postcode", "garaging_postcode", "expected_vehicle_weight",
    "uncertainty_kind",
)
EXPORTED_COLUMNS = (*DEFAULT_COLUMNS,"is_synthetic")


def _arrow_filter(filters: Mapping[str, str | Iterable[str]] | None):
    import pyarrow.compute as pc

    if filters is None:
        return None
    expression = None
    for name, selection in filters.items():
        if name not in FILTER_DIMS:
            raise ValueError(f"Unrecognised or disallowed population filter: {name}")
        if isinstance(selection,str):
            requested = [selection]
        elif isinstance(selection,(tuple,list,set,frozenset)) and all(isinstance(x,str) for x in selection):
            requested = sorted(set(selection))
        else:
            raise ValueError(f"Filter {name} requires a text value or a list of text category values")
        if not requested or any(not x for x in requested):
            raise ValueError("Empty filtered categories are not valid population interpretations")
        part = pc.field(name).isin(requested)
        expression = part if expression is None else expression & part
    return expression


class PopulationStore:
    """Immutable population release FeatureProvider port.

    Construct using an exact release_id, then request typed Arrow batches.
    This class contains no M1.3b/M1.4b sampling or fitting implementation.
    """

    def __init__(self, release_id: str, *, root: Path=ROOT):
        self.root=root
        self.report=verify_population(root,release_id)
        self.release_id=release_id
        self.manifest=self.report["manifest"]
        self.quality=self.report["quality"]
        self.file=Path(self.report["directory"])/OUTPUT_FILES[0]
        self.fourway_controls=Path(self.report["directory"])/OUTPUT_FILES[1]

    @property
    def dataset_schema_version(self) -> str:
        return self.manifest["dataset_schema_version"]

    @property
    def reference_date(self) -> str:
        return self.manifest["reference_date"]

    def pin(self) -> dict:
        """Portable, minimal, immutable dependency for future scenario manifests."""
        asset=self.manifest["outputs"][0]
        return {
            "contract_version":"population-selection-v1",
            "population_release_id":self.release_id,
            "population_asset_sha256":asset["content_sha256"],
            "population_release_digest":self.manifest["release_content_sha256"],
            "dataset_schema_version":self.dataset_schema_version,
            "reference_date":self.reference_date,
            "representation":"weighted_sample",
            "vehicle_weight_field":"expected_vehicle_weight",
            "expected_registered_vehicle_mass":asset["weighted_vehicle_count"],
            "sample_row_count":asset["row_count"],
            "quality_status":"research_only_unapproved_high_dimensional",
            "commercial_use_approved":False,
        }

    def _scanner(self, *, columns: Iterable[str], filters=None, batch_size: int=25000):
        import pyarrow.dataset as ds
        if batch_size<=0 or batch_size>100_000:
            raise ValueError("Population batch size must be 1..100000")
        available=set(self.manifest["outputs"][0].get("schema_fields",EXPORTED_COLUMNS))
        # The raw table may carry all M1.3b data columns, but consumers can
        # only select the advertised stable typed population contract.
        chosen=tuple(columns)
        if len(chosen)!=len(set(chosen)) or not chosen or not set(chosen)<=set(EXPORTED_COLUMNS):
            raise ValueError("Feature view includes unknown/duplicate/empty population field")
        return ds.dataset(self.file,format="parquet").scanner(
            columns=list(chosen), filter=_arrow_filter(filters),
            batch_size=batch_size, use_threads=False,
        )

    def iter_fleet(self, *, columns: Iterable[str]=DEFAULT_COLUMNS,
                   filters: Mapping[str,str|list[str]]|None=None,
                   batch_size: int=25000):
        """Return raw frozen Arrow RecordBatches with no implicit weight=1."""
        yield from self._scanner(columns=columns,filters=filters,batch_size=batch_size).to_batches()

    def iter_feature_view(self, *, filters=None,batch_size: int=25000):
        """Stable synthetic risk *base* view for M2, not a pricing quote."""
        import pyarrow as pa
        cols=(
            "synthetic_row_id", *FILTER_DIMS,
            "expected_vehicle_weight", "uncertainty_kind", "is_synthetic",
        )
        for batch in self.iter_fleet(columns=cols,filters=filters,batch_size=batch_size):
            n=batch.num_rows
            mapped={}
            for field in cols:
                if field == "synthetic_row_id":
                    target="synthetic_vehicle_id"
                elif field == "expected_vehicle_weight":
                    target="sampling_weight"
                else:
                    target=field
                mapped[target]=batch.column(cols.index(field))
            mapped["population_release_id"]=pa.array([self.release_id]*n,pa.string())
            mapped["reference_date"]=pa.array([self.reference_date]*n,pa.string())
            yield pa.record_batch(list(mapped.values()),names=list(mapped.keys()))

    def preview(self, *, limit: int=50,filters=None) -> list[dict]:
        if not 1<=limit<=500:
            raise ValueError("Preview must be limited to 1..500 synthetic rows")
        result=[]
        for batch in self.iter_fleet(filters=filters,batch_size=min(500,limit)):
            for record in batch.to_pylist():
                result.append(record)
                if len(result)>=limit:
                    return result
        return result

    def aggregate(self, *, group_by: Iterable[str]=(),
                  filters: Mapping[str,str|list[str]]|None=None,
                  max_groups: int=100) -> dict:
        """Weighted population accounting with synthetic-support diagnostics.

        Only declared category fields may be used. A zero-row subset does
        not prove there are no such physical Australian vehicles.
        """
        dimensions=tuple(group_by)
        if (len(dimensions)!=len(set(dimensions))
            or len(dimensions)>3 or any(k not in FILTER_DIMS for k in dimensions)
            or not 1<=max_groups<=1000):
            raise ValueError("Invalid aggregation dimension or group count")
        requested=(*dimensions,"expected_vehicle_weight")
        mass=defaultdict(float)
        squares=defaultdict(float)
        counts=defaultdict(int)
        for batch in self.iter_fleet(columns=requested,filters=filters):
            values=batch.to_pydict()
            for i in range(batch.num_rows):
                key=tuple(values[d][i] for d in dimensions)
                weight=float(values["expected_vehicle_weight"][i])
                if not math.isfinite(weight) or weight<=0:
                    raise ValueError("Nonfinite/invalid released weight")
                mass[key]+=weight
                squares[key]+=weight*weight
                counts[key]+=1
        series=[]
        for key, weighted in mass.items():
            ess=weighted**2/squares[key] if squares[key]>0 else 0.0
            support=counts[key]
            series.append({
                "dimensions":dict(zip(dimensions,key)),
                "estimated_registered_vehicles":weighted,
                "synthetic_sample_rows":support,
                "effective_sample_size":ess,
                "support_status":(
                    "low_synthetic_support" if ess<30 or support<30
                    else "exploratory_unvalidated_high_dimensional"
                ),
            })
        series.sort(key=lambda r:(-r["estimated_registered_vehicles"],
                                  str(r["dimensions"])))
        total=sum(mass.values())
        square_total=sum(squares.values())
        return {
            "population_release_id":self.release_id,
            "dataset_schema_version":CONTRACT,
            "group_by":list(dimensions),
            "filters":dict(filters or {}),
            "total_estimated_registered_vehicles":total,
            "total_synthetic_rows":sum(counts.values()),
            "total_effective_sample_size":total**2/square_total if square_total else 0.0,
            "returned_groups":series[:max_groups],
            "omitted_group_count":max(0,len(series)-max_groups),
            "is_individually_observed_vehicle_data":False,
            "is_insurance_exposure_or_addressable_market":False,
            "quality_disclaimer":(
                "Weighted synthetic registrations, not physical vehicle or policy counts. "
                "Finite-sample support and unquantified conditional model uncertainty "
                "prevent precise make/model/postcode-level market-size claims."
            ),
        }
