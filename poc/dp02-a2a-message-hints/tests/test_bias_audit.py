import json
from pathlib import Path

from dp03_a2a_hints.batch_runner import run_scenario_matrix, write_batch_outputs
from dp03_a2a_hints.bias_audit import audit_scenario_bias, write_bias_audit
from dp03_a2a_hints.scenario_generator import generate_scenarios, write_scenarios


def test_bias_audit_reports_distribution_and_warnings(tmp_path):
    scenario_dir = tmp_path / "scenarios"
    result_dir = tmp_path / "results"
    write_scenarios(generate_scenarios(variant_count=2)[:4], scenario_dir)

    records, comparisons = run_scenario_matrix(scenario_dir)
    output = write_batch_outputs(records, comparisons, result_dir)
    audit = audit_scenario_bias(scenario_dir, Path(output["scenario_comparison"]))
    audit_path = result_dir / "bias_audit.json"
    write_bias_audit(audit, audit_path)
    persisted = json.loads(audit_path.read_text(encoding="utf-8"))

    assert audit["scenario_count"] == 4
    assert audit["matrix_distribution"]["task_family"] == {"schedule_coordination": 4}
    assert "issue_occurrences" in audit["domain_distribution"]
    assert "hard_constraint_by_agent" in audit["profile_distribution"]
    assert "agreement_region_ratio_bins" in audit["difficulty_distribution"]
    assert audit["result_correlation"]["scenario_count"] == 4
    assert persisted["scenario_count"] == audit["scenario_count"]
    assert any(warning["code"] == "no_hint_policy_negative_control" for warning in audit["bias_warnings"])
