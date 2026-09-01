from zonecap.exp26 import (
    REQUIRED_STAGES,
    InstrumentedSanityPipeline,
    check_activation_audit,
    distribution,
    nearest_rank,
)


def test_nearest_rank_has_no_interpolation():
    values = [40, 10, 30, 20]
    assert nearest_rank(values, 0.50) == 20
    assert nearest_rank(values, 0.75) == 30
    assert nearest_rank(values, 0.99) == 40


def test_distribution_retains_exact_sample_count_and_bounds():
    result = distribution([5, 1, 3, 2, 4])
    assert result["samples"] == 5
    assert result["minimum_ns"] == 1
    assert result["p50_ns"] == 3
    assert result["maximum_ns"] == 5
    assert result["zero_or_negative_samples"] == 0


def test_full_pipeline_activates_every_required_check():
    pipeline = InstrumentedSanityPipeline()
    _, active = pipeline.evaluate()
    assert active == REQUIRED_STAGES


def test_disabled_check_detector_kills_each_single_stage_mutant():
    audit, _ = check_activation_audit(InstrumentedSanityPipeline())
    assert audit["full_missing_stages"] == []
    assert audit["mutants"] == len(REQUIRED_STAGES)
    assert audit["mutants_killed"] == len(REQUIRED_STAGES)
    assert all(record["detected"] for record in audit["records"])

