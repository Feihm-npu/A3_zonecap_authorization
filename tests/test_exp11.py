from zonecap.exp11 import run_matrix


def test_exp11_matrix_has_no_unexpected_sanity_outcome(tmp_path):
    matrix = run_matrix(tmp_path / "fixtures")
    assert len(matrix["compile_cases"]) == 11
    assert len(matrix["decision_cases"]) == 11
    assert all(case["expectation_match"] for case in matrix["compile_cases"])
    assert all(case["expectation_match"] for case in matrix["decision_cases"])
