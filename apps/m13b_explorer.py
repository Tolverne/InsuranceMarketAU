"""M1.3b synthetic weighted fleet explorer with make/model and postcode filters.

Loaded automatically by apps/m13_explorer.py after M1.3b model generation.
Only local generated weighted synthetic cells are ever shown; no source VIN,
personal record or raw state registration extract is read by this viewer.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/m13b/weighted-synthetic-fleet.parquet"
REPORT = ROOT / "data/reports/m13b/validation.json"
st.set_page_config(page_title="InsuranceMarketAU | Synthetic Fleet Explorer", layout="wide")
st.title("Australian vehicle market — synthetic fleet explorer")
st.caption(
    "BITRE 31 January 2026 • expected vehicle weights • "
    "state, vehicle type, manufacture year, fuel, make, model and separate postcode roles"
)
if not SOURCE.is_file() or not REPORT.is_file():
    st.error("No M1.3b sample found. Run: py -3 scripts/m13b_expand.py --rows 220000")
    st.stop()

@st.cache_data(show_spinner=False)
def get_data(src: str, report_path: str, sample_mtime_ns: int, report_mtime_ns: int):
    table = pq.read_table(src).to_pandas()
    meta = json.loads(Path(report_path).read_text(encoding="utf-8"))
    return table, meta


df, evidence = get_data(str(SOURCE), str(REPORT), SOURCE.stat().st_mtime_ns, REPORT.stat().st_mtime_ns)
if (not df["is_synthetic"].all()
    or evidence["status"] != "weighted_synthetic_analytic_POC_not_fleet_release"
    or len(df) != evidence["rows"]):
    st.error("The local sample has not passed the M1.3b safety/lineage contract.")
    st.stop()

st.warning(
    "**Not an observed make/model/postcode vehicle register.** Model and postcode "
    "relationships are inferred from several separately published aggregate tables. "
    "Registered and garaging postcodes are different location variables and their "
    "pair is not observed jointly. Small selections can be highly variable.",
    icon="⚠️",
)
with st.sidebar:
    st.header("Fleet filters")
    all_states = sorted(df["registered_state"].dropna().unique().tolist())
    selected_states = st.multiselect("State of registration", all_states, default=all_states)
    all_classes = sorted(df["vehicle_type"].dropna().unique().tolist())
    selected_classes = st.multiselect("BITRE vehicle type", all_classes, default=all_classes)
    all_fuels = sorted(df["motive_power"].dropna().unique().tolist())
    selected_fuels = st.multiselect("Motive power / fuel", all_fuels, default=all_fuels)
    st.divider()
    years = pd.to_numeric(df["manufacture_year"], errors="coerce")
    known = years.dropna().astype(int)
    left_year = int(known.min()) if len(known) else 1900
    right_year = int(known.max()) if len(known) else 2026
    left_year = max(1700, min(1900, left_year))
    right_year = max(2026, right_year)
    year_range = st.slider("Manufacture year", min_value=left_year,
                           max_value=right_year, value=(left_year,right_year))
    include_unknown_year = st.checkbox("Include unclassified manufacture year", value=True)
    minimum_age = st.slider("Minimum vehicle age (years at January 2026)", 0, 100, 0)
    st.divider()
    eligible = df[
        df["registered_state"].isin(selected_states)
        & df["vehicle_type"].isin(selected_classes)
        & df["motive_power"].isin(selected_fuels)
    ]
    makes = sorted(eligible["make"].dropna().unique().tolist())
    selected_makes = st.multiselect("Make (optional)", makes, placeholder="All makes")
    model_options = sorted(
        eligible[eligible["make"].isin(selected_makes)]["model"].dropna().unique().tolist()
        if selected_makes else eligible["model"].dropna().unique().tolist()
    )
    # When no make is selected, allow a full text search first; loading a
    # giant model dropdown is cumbersome in the browser.
    model_search = st.text_input("Model name contains (optional)", value="")
    matches = [m for m in model_options if model_search.casefold() in m.casefold()]
    selected_models = st.multiselect("Models (optional)", matches[:2000],
                                     placeholder="All models unless selected")
    st.divider()
    st.caption("Two separate postcode fields: registered ≠ garaged")
    registered_filter = st.text_input("Registration postcode(s)", placeholder="e.g. 4000, 4001")
    garaging_filter = st.text_input("Garaging postcode(s)", placeholder="e.g. 4000, 4001")
    st.caption("Comma-separated exact published postcode labels; empty means all.")


def parse_codes(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


mask = (
    df["registered_state"].isin(selected_states)
    & df["vehicle_type"].isin(selected_classes)
    & df["motive_power"].isin(selected_fuels)
)
numerical_year = pd.to_numeric(df["manufacture_year"], errors="coerce")
mask &= (numerical_year.between(*year_range)
         | (numerical_year.isna() if include_unknown_year else False))
if minimum_age:
    mask &= numerical_year.le(2026 - minimum_age)  # Unknown year cannot establish a minimum age.
if selected_makes:
    mask &= df["make"].isin(selected_makes)
if selected_models:
    mask &= df["model"].isin(selected_models)
if model_search:
    mask &= df["model"].str.contains(model_search, case=False, regex=False, na=False)
codes = parse_codes(registered_filter)
if codes:
    mask &= df["registered_postcode"].isin(codes)
codes = parse_codes(garaging_filter)
if codes:
    mask &= df["garaging_postcode"].isin(codes)
selected = df[mask].copy()
weight = "expected_vehicle_weight"
expected = float(selected[weight].sum())
sample_count = len(selected)
ess = expected**2 / float(np.square(selected[weight].to_numpy()).sum()) if expected > 0 else 0.0
a,b,c,d = st.columns(4)
a.metric("Modelled expected vehicles", f"{expected:,.0f}")
b.metric("National accounting benchmark", f"{evidence['national_published_accounting_anchor']:,}")
c.metric("Synthetic observations selected", f"{sample_count:,}")
d.metric("Effective sample size (ESS)", f"{ess:,.0f}")
st.caption(
    "Expected vehicles = sum of calibrated sample weights, not number of "
    "published vehicles or fitted individual-car records. "
    "ESS measures sample-weight concentration, not model validity."
)
if sample_count == 0:
    st.info("No synthetic observations matched those filters. This is not proof that the actual market has no such vehicles.")
    st.stop()
if sample_count < 30 or ess < 30:
    st.warning(
        "Only a small number of weighted synthetic observations support this "
        "selection. The modelled estimate is unstable for this rare cohort; "
        "a dedicated model/segment analysis is required."
    )
elif sample_count < 100 or ess < 100:
    st.info("This subset has modest synthetic support. Interpret the count as an exploratory estimate.")
st.caption(f"Selected expected share of the national BITRE accounting anchor: {100*expected/evidence['national_published_accounting_anchor']:.4f}%")

def chart(frame: pd.DataFrame, dimension: str, *, n: int = 20) -> None:
    series = frame.groupby(dimension,dropna=False)[weight].sum().sort_values(ascending=False).head(n)
    st.bar_chart(series, y_label="Weighted synthetic expected vehicles")


overview, makes_tab, geography, sample_rows_tab, validation = st.tabs([
    "Overview", "Make and model", "Registered versus garaging geography", "Synthetic sample rows", "Validation and provenance"
])
with overview:
    x,y = st.columns(2)
    with x:
        st.subheader("Vehicle class")
        chart(selected, "vehicle_type")
        st.subheader("State of registration")
        chart(selected, "registered_state")
    with y:
        st.subheader("Motive power")
        chart(selected, "motive_power")
        st.subheader("Year of manufacture")
        numeric = pd.to_numeric(selected["manufacture_year"], errors="coerce")
        chronological = selected.assign(numeric_year=numeric).dropna(subset=["numeric_year"])
        if not chronological.empty:
            by_year = chronological.groupby(chronological["numeric_year"].astype(int))[weight].sum()
            st.line_chart(by_year, y_label="Expected vehicles")

with makes_tab:
    x,y = st.columns(2)
    with x:
        st.subheader("Top makes")
        chart(selected,"make",n=25)
    with y:
        st.subheader("Top make/model combinations")
        models = selected.groupby(["make","model"],dropna=False)[weight].agg(["sum","count"])
        models = models.sort_values("sum",ascending=False).head(40).reset_index()
        models.columns=["Make","Model","Modelled vehicles","Sample observations"]
        st.dataframe(models,hide_index=True,use_container_width=True)
    st.caption(
        "Model-year-fuel associations are conditioned from independent published "
        "projections, with explicit fallback when no exact source-conditioned "
        "group exists. These are NOT source-linked original vehicle combinations."
    )

with geography:
    a,b=st.columns(2)
    with a:
        st.subheader("Postcode of registration")
        chart(selected,"registered_postcode",n=25)
        st.caption("From BITRE registration postcode projections B26-04/06/08/13.")
    with b:
        st.subheader("Garaging postcode")
        chart(selected,"garaging_postcode",n=25)
        st.caption(
            "From BITRE garaging postcode projection B26-09. It may incorporate "
            "publisher fallbacks. The pair of postcodes is simulated, not observed."
        )
    st.info(
        "Postcodes are category labels from source publications. "
        "No postcode-to-suburb translation or address/geocoder claim is made."
    )

with sample_rows_tab:
    st.subheader("Synthetic analytic sample (first 500 matching rows)")
    st.caption(
        "These are algorithmically simulated weighted attribute combinations, "
        "NOT real registered vehicle records. A row weight is expected vehicles, "
        "not a count of source records or the probability of one observed car."
    )
    cols = ["registered_state", "vehicle_type", "manufacture_year", "motive_power",
            "make", "model", "registered_postcode", "garaging_postcode",
            "expected_vehicle_weight"]
    st.dataframe(selected[cols].head(500), hide_index=True, use_container_width=True)

with validation:
    st.subheader("Model provenance and calibration")
    st.write("M1.3a base: BITRE B26-01, B26-02 and B26-03; Table 1 operational accounting controls.")
    st.write("M1.3b conditional training: " + ", ".join(evidence["training_projections"]))
    st.write("High-order sources withheld from conditional estimation: " +
             ", ".join(evidence["heldout_projections_excluded_from_sampling"]))
    st.write("Published source hashes, output weights and observed fallback counts are stored in the local M1.3b report.")
    if evidence.get("heldout_validation"):
        st.dataframe(pd.DataFrame(evidence["heldout_validation"]),hide_index=True,use_container_width=True)
    st.json({
        "observation_date":evidence["reference_date"],
        "model_output":evidence["status"],
        "source_microdata_linkage_performed":evidence["source_microdata_linkage_performed"],
        "published_reg_postcode_and_garage_pair_observed":False,
        "fourway_base_mass":evidence["weighted_total_expected"],
        "fallback_counts":evidence["quality"]["fallback_counts"],
        "unknown_counts":evidence["quality"]["unknown_attribute_counts"],
    })
    st.caption(
        "Source suppression may perturb positive and zero published counts. "
        "These synthetic values are exploratory, not an insurer pricing-rate table."
    )
