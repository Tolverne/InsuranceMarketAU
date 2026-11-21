"""M1.2 synthetic data-source and disclosure regression tests."""
from __future__ import annotations

from io import BytesIO
import hashlib,json
from pathlib import Path
from zipfile import ZipFile
import pytest
from insurance_market_au.data_foundation.m12 import (
    count_token,parse_date,zip_member_date,match_source,load_registry,
    select_sources,run_m12,
)


def root_fixture(root:Path)->dict:
    config=load_registry()
    f=root/"catalog/harmonization/m12-sources.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(config),encoding="utf-8")
    controls=root/"data/processed/m1/controls/bitre-2026-table1-controls.json"
    controls.parent.mkdir(parents=True)
    states={"NSW":6502052,"Vic":5795388,"Qld":5020772,"SA":1664049,
            "WA":2704554,"Tas":561458,"NT":173660,"ACT":349217}
    controls.write_text(json.dumps({"national_total":22771150,"reference_date":"2026-01-31",
        "controls":[{"state":s,"vehicle_type":"Total motor vehicles","vehicles":v}
                    for s,v in states.items()]}))
    return config


def acquired(root:Path,sid:str,group:str,vintage:str,data:bytes)->Path:
    digest=hashlib.sha256(data).hexdigest()
    folder=root/"data/raw"/group/vintage
    folder.mkdir(parents=True,exist_ok=True)
    ext="zip" if data.startswith(b"PK") else "csv"
    f=folder/(sid[:70]+"--"+digest[:12]+"."+ext)
    f.write_bytes(data)
    out=root/"data/reports"/f"acquisition-test-{sid}.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"mode":"download","resources":[{
        "status":"downloaded","source_id":sid,"sha256":digest,
        "path":str(f.relative_to(root))}]}))
    return f


def test_published_censoring_not_zero():
    assert count_token("<=5","COUNT")=={
        "status":"right_censored_published_upper_bound","count":None,"lower":0,"upper":5}
    assert count_token("≤10","Count")["upper"]==10
    assert count_token("0","TOTAL1")["count"]==0
    assert count_token("2,304","TOTAL1")["count"]==2304
    assert count_token("?", "COUNT")["status"]=="unrecognised_count_token_requires_review"
    assert count_token(None,None)["status"]=="unverified_grain_no_count_inferred"


def test_month_dates_are_distinct_and_validated():
    assert zip_member_date("TfNSW_Usage_202601_1.csv")=="2026-01-31"
    assert zip_member_date("TfNSW_Usage_202602_2.csv")=="2026-02-28"
    with pytest.raises(ValueError):
        zip_member_date("TfNSW_Usage_202501_1.csv")
    assert parse_date("21/11/2026")=="2026-11-21"
    assert parse_date("2026-11-21T00:00:00.000")=="2026-11-21"


def test_source_types_and_avoided_geography_conflation():
    cfg=load_registry()
    assert match_source(cfg,"vic_postcode_q3_2026")["geography_role"]=="garaging_postcode"
    assert match_source(cfg,"vic_model_q3_2026")["geography_role"]=="not_present"
    assert match_source(cfg,"sa_registered_postcode_2026__uuid")["geography_role"]=="owner_postcode"
    assert match_source(cfg,"nsw_transactions_2026")["kind"]=="flow"
    assert match_source(cfg,"qld_registration_2022__x")["measure_col"] is None
    assert match_source(cfg,"nsw_age_2026")["tier"]=="quarantined"


def test_vic_parquet_preserves_unmapped_class_and_date(tmp_path:Path):
    pa=pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    root_fixture(tmp_path)
    sid="vic_postcode_q3_2026"
    data=("CD_MAKE_VEH1,CD_CLASS_VEH,NB_YEAR_MFC_VEH,POSTCODE,CD_CL_FUEL_ENG,TOTAL1\n"
          "TOYOTA,2,1998,4000,D,4\nFORD,2,1966,2000,P,0\n").encode()
    acquired(tmp_path,sid,"vic","2026-09-30",data)
    report=run_m12(root=tmp_path,groups={"vic"},parquet=True,only_source=sid,fail_on_error=True)
    x=report["source_profiles"][0]
    assert x["count_sum_numeric"]==4 and x["source_rows"]==2
    assert x["alignment_to_bitre"]["direct_count_difference_computed"] is False
    rows=pq.read_table(x["parquet_file"]).to_pylist()
    assert rows[0]["geography_value"]=="4000"
    assert rows[0]["source_vehicle_class"]=="2"
    assert rows[0]["candidate_bitre_class"] is None
    assert rows[0]["observation_date"]=="2026-09-30"
    assert rows[1]["published_count"]==0


def test_nsw_monthly_zip_and_suppressed_bounds(tmp_path:Path):
    pytest.importorskip("pyarrow")
    root_fixture(tmp_path)
    sid="nsw_usage_2026"
    header='"VEHICLE TYPE"|"HIGH LEVEL USAGE"|"TERM OF REGISTRATION"|"PLATE TYPE"|"CUSTOMER ADDRESS LGA"|"COUNT"\n'
    member='"Forward-control Passenger Vehicle"|"Private"|"Annual"|"Standard"|"Sydney"|"<=5"\n'
    stream=BytesIO()
    with ZipFile(stream,"w") as z:
        z.writestr("TfNSW_Registered_Vehicles_by_Usage_Snapshot_202601_1.csv",header+member)
        z.writestr("TfNSW_Registered_Vehicles_by_Usage_Snapshot_202602_1.csv",
                   header+member.replace('"<=5"','"8"'))
    acquired(tmp_path,sid,"nsw","2026",stream.getvalue())
    report=run_m12(root=tmp_path,groups={"nsw"},only_source=sid,parquet=True,fail_on_error=True)
    x=report["source_profiles"][0]
    assert x["source_rows"]==2 and x["censored_rows"]==1
    assert x["sum_known_lower_bound"]==8 and x["sum_known_upper_bound"]==13
    assert x["cross_month_total_is_not_a_fleet_total"]
    assert set(x["observed_dates"])=={"2026-01-31","2026-02-28"}
    assert any(n["source_id"]=="nsw_age_2026" for n in report["notices"])


def test_sa_mirror_is_not_counted_twice(tmp_path:Path):
    cfg=root_fixture(tmp_path)
    data=("Owner PostCode,Vehicle Make,Vehicle Body Type,Vehicle Number of Cylinders,"
          "Vehicle Year of Manufacture,Count of Vehicle ROIDs,Total(TOTAL_VEHICLES)\n"
          "0800,HOLDEN,UTILITY,4 Cylinders,2018,1,\n"
          "5000,TOYOTA,TRAILER,,2000,7,\n").encode()
    sid="sa_registered_postcode_2026__test"
    acquired(tmp_path,sid,"sa","2026-06-30",data)
    acquired(tmp_path,"sa_original_2026_mirror","sa_mirror","2026-06-30",data)
    selected,notes=select_sources(tmp_path,cfg,{"sa"})
    assert len(selected)==1 and selected[0]["source_id"]==sid
    assert any(n["status"]=="mirror_checksum_matches_official" for n in notes)
    r=run_m12(root=tmp_path,groups={"sa"},fail_on_error=True)
    assert r["source_profiles"][0]["count_sum_numeric"]==8
    assert r["source_profiles"][0]["geography_role"]=="owner_postcode"


def test_qld_unverified_row_grain_does_not_infer_vehicle_counts(tmp_path:Path):
    root_fixture(tmp_path)
    acquired(tmp_path,"qld_registration_2022__fake","qld","2022-10-10",
             b"VIN,REGISTRATION,MAKE\nsecret,a,TOYOTA\nsecret,b,HOLDEN\n")
    r=run_m12(root=tmp_path,groups={"qld"},fail_on_error=True)
    p=r["source_profiles"][0]
    assert p["source_rows"]==2
    assert p["count_sum_numeric"]==0 and p["unknown_count_rows"]==2
    assert p["schema_review_needed"] is True


def test_source_sha_and_physical_header_drift_rejected(tmp_path:Path):
    root_fixture(tmp_path)
    sid="vic_model_q3_2026"
    path=acquired(tmp_path,sid,"vic","2026-09-30",
                  b"CD_MAKE_VEH1,CD_MODEL_VEH,CD_CLR_BDY_VEH_P,TOTAL1\nFord,F,Blue,2\n")
    path.write_bytes(path.read_bytes()+b"extra")
    r=run_m12(root=tmp_path,groups={"vic"},only_source=sid)
    assert len(r["source_failures"])==1
    assert "SHA drift" in r["source_failures"][0]["error"]
    assert r["source_profiles"]==[]


def test_act_manually_downloaded_official_schema_and_dates(tmp_path:Path):
    pytest.importorskip("pyarrow")
    cfg=root_fixture(tmp_path)
    contents=(
        "Data as at,Suburb,Make,Model,Emissions Category,Count\n"
        "2026-11-01,Canberra,Toyota,Corolla,Petrol,<=10\n"
        "2026-11-01,Belconnen,Volvo,XC60,Petrol,25\n"
    ).encode()
    digest=hashlib.sha256(contents).hexdigest()
    spec=match_source(cfg,"act_make_model_suburb")
    spec["manual_sha256"]=digest
    (tmp_path/"catalog/harmonization/m12-sources.json").write_text(json.dumps(cfg))
    folder=tmp_path/"data/raw/act/2026"
    folder.mkdir(parents=True)
    (folder/"act-make-model-suburb-manual.csv").write_bytes(contents)
    r=run_m12(root=tmp_path,groups={"act"},parquet=True,fail_on_error=True)
    profile=r["source_profiles"][0]
    assert profile["manual_acquisition"] is True
    assert profile["source_rows"]==2
    assert profile["censored_rows"]==1
    assert profile["observed_dates"]["2026-11-01"]["upper_sum_known"]==35
    assert profile["geography_role"]=="published_suburb_role_unverified"


def test_nsw_transaction_flow_excluded_from_stock(tmp_path:Path):
    pytest.importorskip("pyarrow")
    root_fixture(tmp_path)
    sid="nsw_transactions_2026"
    head='"VEHICLE REGISTRATION TRANSACTION TYPE"|"CUSTOMER TYPE"|"MANUFACTURER"|"FUEL TYPE"|"COLOUR"|"TRANSFER TYPE"|"GENDER"|"AGE GROUP"|"CUSTOMER ADDRESS LGA"|"COUNT"\n'
    row='"Establish registration of new vehicle"|"Private"|"Toyota"|"Petrol"|"Blue"|"New"|"N/A"|"N/A"|"Sydney"|"12"\n'
    stream=BytesIO()
    with ZipFile(stream,"w") as z:
        z.writestr("TfNSW_Vehicle_Registration_Transactions_202601_1.csv",head+row)
    acquired(tmp_path,sid,"nsw","2026",stream.getvalue())
    r=run_m12(root=tmp_path,groups={"nsw"},only_source=sid,parquet=True,fail_on_error=True)
    assert r["stock_sources"]==[]
    assert r["flow_sources_excluded_from_stock"]==[sid]
    p=r["source_profiles"][0]
    assert p["alignment_to_bitre"]["date_and_scope_classification"]["2026-01-31"]=="not_comparable_flow_vs_stock"
    assert "/flow/" in p["parquet_file"].replace("\\","/")


def test_sa_mirror_fallback_must_stay_separate(tmp_path:Path):
    cfg=root_fixture(tmp_path)
    contents=("Owner PostCode,Vehicle Make,Vehicle Body Type,Vehicle Number of Cylinders,"
        "Vehicle Year of Manufacture,Count of Vehicle ROIDs,Total(TOTAL_VEHICLES)\n"
        "5000,TOYOTA,SEDAN,4 Cylinders,2020,7,\n").encode()
    acquired(tmp_path,"sa_original_2026_mirror","sa_mirror","2026-06-30",contents)
    selected,warnings=select_sources(tmp_path,cfg,{"sa"})
    assert len(selected)==1
    assert selected[0]["source_id"]=="sa_original_2026_mirror"
    assert any(x["status"]=="third_party_mirror_fallback" for x in warnings)
    profile=run_m12(root=tmp_path,groups={"sa"})["source_profiles"][0]
    assert profile["source_rows"]==1
    assert profile["source_tier"]=="fallback_only"


def test_coverage_matrix_preserves_bitre_only_jurisdictions(tmp_path:Path):
    root_fixture(tmp_path)
    sid="vic_model_q3_2026"
    acquired(tmp_path,sid,"vic","2026-09-30",
             b"CD_MAKE_VEH1,CD_MODEL_VEH,CD_CLR_BDY_VEH_P,TOTAL1\nVolvo,XC60,White,3\n")
    run_m12(root=tmp_path,groups={"vic"},fail_on_error=True)
    matrix=json.loads((tmp_path/"data/reports/m12/coverage-matrix.json").read_text())
    assert matrix["national_bitre_registered_motor_vehicles"]==22771150
    by={x["registration_jurisdiction"]:x for x in matrix["jurisdictions"]}
    assert len(by)==8
    for state in ("WA","Tas","NT"):
        assert by[state]["supplemental_status"]=="bitre_only_no_additional_granular_local_source"
        assert by[state]["bitre_2026_01_registered_motor_vehicles"]>0
    assert by["Vic"]["stock_source_ids"]==[sid]
    assert not by["Vic"]["approved_bitre_class_crosswalk"]


def test_two_vic_projections_can_reconcile_totals_without_row_join(tmp_path:Path):
    root_fixture(tmp_path)
    postcode=("CD_MAKE_VEH1,CD_CLASS_VEH,NB_YEAR_MFC_VEH,POSTCODE,CD_CL_FUEL_ENG,TOTAL1\n"
              "VOLVO,2,2021,4000,D,4\n").encode()
    model=("CD_MAKE_VEH1,CD_MODEL_VEH,CD_CLR_BDY_VEH_P,TOTAL1\n"
           "VOLVO,XC60,White,4\n").encode()
    acquired(tmp_path,"vic_postcode_q3_2026","vic","2026-09-30",postcode)
    acquired(tmp_path,"vic_model_q3_2026","vic","2026-09-30",model)
    r=run_m12(root=tmp_path,groups={"vic"},fail_on_error=True)
    assert r["within_publisher_checks"][0]["status"]=="published_aggregate_counts_agree"
    assert r["within_publisher_checks"][0]["delta_model_minus_postcode"]==0
    assert r["within_publisher_checks"][0]["not_a_vehicle_row_join"]
    pilot=run_m12(root=tmp_path,groups={"vic"},limit_rows=1,fail_on_error=True)
    assert pilot["within_publisher_checks"][0]["status"]=="not_evaluated_partial_sample"


def test_requested_but_missing_source_not_silently_complete(tmp_path:Path):
    root_fixture(tmp_path)
    sid="vic_model_q3_2026"
    acquired(tmp_path,sid,"vic","2026-09-30",
             b"CD_MAKE_VEH1,CD_MODEL_VEH,CD_CLR_BDY_VEH_P,TOTAL1\nA,B,C,2\n")
    result=run_m12(root=tmp_path,groups={"vic"},fail_on_error=True)
    assert result["source_inventory_complete"] is False
    assert any(x["source_id"]=="vic_postcode_q3_2026"
               and x["status"]=="requested_source_missing" for x in result["notices"])
    pilot=run_m12(root=tmp_path,groups={"vic"},only_source=sid,fail_on_error=True)
    assert pilot["source_inventory_requested_subset"]
