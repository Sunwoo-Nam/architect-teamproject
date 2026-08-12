"""결과 형식 — dp2의 재현성(run_id·메타·자동 리포트)과 dpca의 추적성(케이스별 행)을 합친다."""
from __future__ import annotations

import json

import pytest

from total.qa.report import (
    RunMeta,
    make_run_id,
    render_index,
    render_markdown,
    write_run,
)


def meta(**kw) -> RunMeta:
    base = dict(run_id="run-1", experiment="demo", seed=7,
                dataset={"name": "ds", "n_participants": 3, "n_issues": 4},
                plans=["A", "B"], note="")
    base.update(kw)
    return RunMeta(**base)


RAW = {
    "fc": {"A": {"mean_achieved": 0.91, "stars_achieved": 4, "mean_s": 0.31, "stars_s": 2},
           "B": {"mean_achieved": 0.97, "stars_achieved": 5, "mean_s": 0.74, "stars_s": 4}},
    "tb": {"A": {"median_total_ms": 1950.0, "dominant": "phase"},
           "B": {"median_total_ms": 2212.0, "dominant": "phase"}},
    "ru": {"A": {"median_total_mb": 0.01, "stars_median": 5},
           "B": {"median_total_mb": 0.03, "stars_median": 5}},
}
CASES = [
    {"case_id": "c1", "plan": "A", "achieved": 0.9, "agreed": True},
    {"case_id": "c1", "plan": "B", "achieved": 1.0, "agreed": True},
]


class TestRunId:
    def test_format(self):
        rid = make_run_id("demo", "20260813T010203KST")
        assert rid == "demo-20260813T010203KST"

    def test_sorts_chronologically(self):
        a = make_run_id("x", "20260813T010203KST")
        b = make_run_id("x", "20260813T020203KST")
        assert a < b


class TestRunMeta:
    def test_carries_provenance(self):
        m = meta()
        d = m.as_dict()
        assert d["run_id"] == "run-1" and d["seed"] == 7
        assert "created_at" in d and "python" in d

    def test_records_git_commit_field(self):
        # 커밋을 못 읽는 환경도 있으므로 None 허용 — 키는 항상 있어야 한다
        assert "commit" in meta().as_dict()

    def test_records_constants(self):
        d = meta().as_dict()
        assert d["constants"]["t_phase_ms"] == 75.0


class TestWriteRun:
    def test_creates_all_artifacts(self, tmp_path):
        out = write_run(tmp_path, meta(), RAW, CASES)
        for name in ("meta.json", "raw.json", "cases.jsonl", "report.md", "report.html"):
            assert (out / name).exists(), name

    def test_raw_json_roundtrip(self, tmp_path):
        out = write_run(tmp_path, meta(), RAW, CASES)
        assert json.loads((out / "raw.json").read_text())["fc"]["A"]["stars_achieved"] == 4

    def test_cases_jsonl_is_one_per_line(self, tmp_path):
        out = write_run(tmp_path, meta(), RAW, CASES)
        lines = (out / "cases.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["case_id"] == "c1"

    def test_run_dir_is_namespaced_by_experiment(self, tmp_path):
        out = write_run(tmp_path, meta(experiment="demo", run_id="r9"), RAW, CASES)
        assert out.parent.name == "demo" and out.name == "r9"

    def test_index_updated(self, tmp_path):
        write_run(tmp_path, meta(), RAW, CASES)
        assert (tmp_path / "INDEX.md").exists()

    def test_index_lists_multiple_runs(self, tmp_path):
        write_run(tmp_path, meta(run_id="r1"), RAW, CASES)
        write_run(tmp_path, meta(run_id="r2"), RAW, CASES)
        text = (tmp_path / "INDEX.md").read_text()
        assert "r1" in text and "r2" in text

    def test_empty_cases_allowed(self, tmp_path):
        out = write_run(tmp_path, meta(), RAW, [])
        assert (out / "cases.jsonl").read_text() == ""

    def test_non_ascii_preserved(self, tmp_path):
        out = write_run(tmp_path, meta(note="한글 메모"), RAW, CASES)
        assert "한글 메모" in (out / "meta.json").read_text()


class TestRenderMarkdown:
    def test_has_title_and_plans(self):
        md = render_markdown(meta(), RAW)
        assert "demo" in md and "| A |" in md or "A" in md

    def test_shows_stars_as_symbols(self):
        md = render_markdown(meta(), RAW)
        assert "★" in md

    def test_lists_every_qa_section(self):
        md = render_markdown(meta(), RAW)
        for qa in ("Functional Correctness", "Time Behaviour", "Resource Utilization"):
            assert qa in md

    def test_records_constants_for_provenance(self):
        md = render_markdown(meta(), RAW)
        assert "75" in md          # t_phase

    def test_skips_missing_qa_gracefully(self):
        md = render_markdown(meta(), {"fc": RAW["fc"]})
        assert "Functional Correctness" in md
        assert "Confidentiality" not in md

    def test_warns_on_provisional_bands(self):
        md = render_markdown(meta(), RAW)
        assert "잠정" in md


class TestRenderIndex:
    def test_empty_root(self, tmp_path):
        assert "실행 없음" in render_index(tmp_path)

    def test_row_per_run(self, tmp_path):
        write_run(tmp_path, meta(run_id="r1"), RAW, CASES)
        write_run(tmp_path, meta(run_id="r2", experiment="other"), RAW, CASES)
        text = render_index(tmp_path)
        assert "demo" in text and "other" in text

    def test_newest_first(self, tmp_path):
        write_run(tmp_path, meta(run_id="demo-20260101T000000KST"), RAW, CASES)
        write_run(tmp_path, meta(run_id="demo-20260202T000000KST"), RAW, CASES)
        text = render_index(tmp_path)
        assert text.index("20260202") < text.index("20260101")


class TestValidation:
    def test_rejects_unknown_qa_key(self, tmp_path):
        with pytest.raises(ValueError):
            write_run(tmp_path, meta(), {"nope": {}}, CASES)

    def test_rejects_case_without_plan(self, tmp_path):
        with pytest.raises(ValueError):
            write_run(tmp_path, meta(), RAW, [{"case_id": "c"}])
