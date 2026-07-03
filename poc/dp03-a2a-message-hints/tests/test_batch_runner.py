import json
from pathlib import Path
from shutil import copyfile

from dp03_a2a_hints.batch_runner import run_scenario_matrix, write_batch_outputs


def test_batch_runner_writes_track_a_outputs(tmp_path):
    source_dir = Path("scenarios/generated")
    scenario_dir = tmp_path / "scenarios"
    output_dir = tmp_path / "results"
    scenario_dir.mkdir()
    for path in sorted(source_dir.glob("*.yaml"))[:2]:
        copyfile(path, scenario_dir / path.name)

    records, comparisons = run_scenario_matrix(scenario_dir)
    output = write_batch_outputs(records, comparisons, output_dir)

    assert len(records) == 4
    assert len(comparisons) == 2
    assert Path(output["run_results"]).exists()
    assert Path(output["scenario_comparison"]).exists()
    assert Path(output["metric_summary"]).exists()

    summary = json.loads(Path(output["metric_summary"]).read_text(encoding="utf-8"))

    assert summary["group_summary"]["A1_DET_OFFER_ONLY"]["run_count"] == 2
    assert summary["group_summary"]["A2_DET_HINT_AWARE"]["run_count"] == 2
    assert summary["comparison_summary"]["scenario_count"] == 2
    assert "mean_round_delta_a2_minus_a1" in summary["comparison_summary"]
    assert "tension_pattern" in summary["breakdown_by"]
    assert summary["breakdown_by"]["tension_pattern"]["aligned_preferences"]["scenario_count"] == 2
