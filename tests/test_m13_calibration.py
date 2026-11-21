"""M1.3a synthetic independent-source calibration and holdout tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest

from insurance_market_au.data_foundation.m13 import (
    build_support, constraints_for_joint, enforce_hard_totals, evaluate_holdout,
    fit, margin_metrics, write_joint, write_sample,
)


def example():
    controls = {
        ("NSW","Passenger vehicles"):100.0,
        ("Vic","Passenger vehicles"):120.0,
        ("NSW","Motorcycles"):40.0,
        ("Vic","Motorcycles"):10.0,
    }
    first={}
    fuel={}
    year_fuel={}
    for (state, klass), amount in controls.items():
        for year, scale in (("1990",0.4),("2020",0.6)):
            first[state,klass,year]=amount*scale
        for motive, scale in (("Petrol",0.8),("Electric",0.2)):
            fuel[state,klass,motive]=amount*scale
    for klass in ("Passenger vehicles","Motorcycles"):
        total=sum(amount for (state,vehicle),amount in controls.items() if vehicle==klass)
        for year, p in (("1990",0.4),("2020",0.6)):
            for motive, q in (("Petrol",0.8),("Electric",0.2)):
                year_fuel[klass,year,motive]=total*p*q
    return controls,{"B26-01":first,"B26-02":year_fuel,"B26-03":fuel}


def test_support_is_independent_of_holdout_and_zeros_are_not_structural():
    control,training=example()
    joint=build_support(control,training)
    assert len(joint.weights)==16
    assert set(joint.tuples()) == {
        (s,c,y,f) for s in ("NSW","Vic")
        for c in ("Passenger vehicles","Motorcycles")
        for y in ("1990","2020") for f in ("Petrol","Electric")
    }
    assert np.all(joint.weights>0)
    assert joint.weights.sum()==pytest.approx(270)
    assert not any(name.startswith("B26-10") for name in
                   [c.name for c in constraints_for_joint(joint,training)])


def test_hard_controls_stay_exact_when_soft_targets_conflict():
    controls,training=example()
    training["B26-01"]["NSW","Passenger vehicles","1990"]=70.0
    training["B26-03"]["NSW","Passenger vehicles","Electric"]=45.0
    joint=build_support(controls,training)
    specs=constraints_for_joint(joint,training)
    before=margin_metrics(joint,specs)
    report=fit(joint,specs,iterations=28,relaxation=0.35)
    assert report["maximum_operational_control_error"]<1e-6
    for i,k in enumerate(joint.state_type_labels):
        assert sum(w for j,w in enumerate(joint.weights)
                   if joint.state_type_ids[j]==i)==pytest.approx(controls[k],abs=1e-6)
    assert np.isfinite(joint.weights).all()
    assert np.all(joint.weights>0)
    assert report["formal_disclosure_likelihood_estimated"] is False


def test_holdout_not_fitted_even_if_it_is_adversarial():
    controls,training=example()
    j=build_support(controls,training)
    c=constraints_for_joint(j,training)
    fit(j,c,iterations=20)
    original=j.weights.copy()
    hi={("NSW","Passenger vehicles","1990","Electric"):1000.0}
    report=evaluate_holdout(j,hi)
    assert report["trained_on_holdout"] is False
    assert report["overall_published_cell_wape"]>0
    assert np.array_equal(j.weights,original)  # evaluation does not mutate model


def test_unobserved_year_fuel_pairs_not_assumed_impossible():
    controls,training=example()
    del training["B26-02"]["Passenger vehicles","1990","Electric"]
    joint=build_support(controls,training)
    assert ("NSW","Passenger vehicles","1990","Electric") in set(joint.tuples())
    specs=constraints_for_joint(joint,training)
    fit(joint,specs,iterations=8)
    idx=joint.tuples().index(("NSW","Passenger vehicles","1990","Electric"))
    assert joint.weights[idx]>0


def test_support_size_limit_raises():
    controls,training=example()
    with pytest.raises(ValueError,match="Sparse support exceeds"):
        build_support(controls,training,max_support=5)


def test_sample_is_seeded_and_explicitly_synthetic(tmp_path:Path):
    pa=pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    controls,training=example()
    joint=build_support(controls,training)
    fit(joint,constraints_for_joint(joint,training),iterations=6)
    output=tmp_path/"joint.parquet"
    write_joint(joint,output)
    table=pq.read_table(output)
    assert table.num_rows==16
    assert sum(table["expected_synthetic_vehicles"].to_pylist())==pytest.approx(270)
    assert "VIN" not in table.column_names
    sample_a=tmp_path/"sample-a.parquet"
    sample_b=tmp_path/"sample-b.parquet"
    write_sample(joint,sample_a,n=100,seed=11)
    write_sample(joint,sample_b,n=100,seed=11)
    x=pq.read_table(sample_a)
    y=pq.read_table(sample_b)
    assert x.equals(y)
    assert all(x["is_synthetic"].to_pylist())
    assert "registration_postcode" not in x.column_names
    with pytest.raises(ValueError):
        write_sample(joint,tmp_path/"bad.parquet",n=200001,seed=11)


def test_unknown_source_projection_is_not_a_source_of_model_features():
    controls,training=example()
    before=deepcopy(training)
    before["B26-10"]={("NSW","Passenger vehicles","1990","Electric"):1e8}
    joint1=build_support(controls,training)
    joint2=build_support(controls,before)
    assert np.array_equal(joint1.weights,joint2.weights)
    assert joint1.tuples()==joint2.tuples()
