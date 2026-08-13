"""결과 형식 — 두 PoC의 장점을 합친다.

| 요소 | 출처 | 왜 |
|---|---|---|
| `<experiment>/<run_id>/` + `meta.json` | dp2 | 재현성 — seed·commit·상수가 없으면 결과를 신뢰할 수 없다 |
| `raw.json` + 자동 `report.md`/`.html` + `INDEX.md` | dp2 | 수기 md는 갱신 누락이 생긴다 |
| **`cases.jsonl`** (1케이스 = 1행) | dpca | 집계값만 남기면 개별 케이스를 추적할 수 없다 |

리포트는 **별점만 싣지 않는다** — 여러 밴드가 잠정이므로 원지표를 함께 낸다.
"""
from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .constants import SYNTH_TIME

#: raw.json에 올 수 있는 QA 키. 오타로 만든 섹션이 조용히 리포트에서 빠지는 것을 막는다.
QA_KEYS = ("fc", "ru", "cf", "tb", "sc_issue")  # 핵심 서열 (24 §0, 2026-08-13)

QA_TITLES = {
    "fc": "Functional Correctness (24 §1)",
    "cf": "Confidentiality (24 §3)",
    "tb": "Time Behaviour (24 §4)",
    "ru": "Resource Utilization-메모리 (24 §2)",
    "sc_issue": "Scalability-의제 (24 §5)",
}


def make_run_id(experiment: str, stamp: str) -> str:
    return f"{experiment}-{stamp}"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def _negmas_version() -> str | None:
    try:
        import negmas

        return getattr(negmas, "__version__", None)
    except Exception:
        return None


def stars(n: int | None) -> str:
    if n is None:
        return "—"
    return "★" * n + "☆" * (5 - n) + f" ({n}점)"


def cell(value) -> str:
    """표 한 칸. **`None`을 'None'으로 찍지 않는다** — 안 쟀다는 뜻이 드러나야 한다."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "예" if value else "**아니오**"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


@dataclass
class RunMeta:
    run_id: str
    experiment: str
    seed: int
    dataset: dict
    plans: list[str]
    note: str = ""
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "experiment": self.experiment,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seed": self.seed,
            "dataset": self.dataset,
            "plans": list(self.plans),
            "commit": _git_commit(),
            "negmas": _negmas_version(),
            "python": platform.python_version(),
            "constants": SYNTH_TIME.as_dict(),
            "note": self.note,
            **self.extra,
        }


def _validate(raw: dict, cases: Sequence[dict]) -> None:
    unknown = set(raw) - set(QA_KEYS)
    if unknown:
        raise ValueError(f"알 수 없는 QA 키: {sorted(unknown)} (등록: {list(QA_KEYS)})")
    for i, c in enumerate(cases):
        if "plan" not in c:
            raise ValueError(f"cases[{i}]에 plan이 없다 — 방안 구분 없이는 집계할 수 없다")


def write_run(
    results_root: Path,
    meta: RunMeta,
    raw: dict,
    cases: Sequence[dict],
) -> Path:
    """`results/<experiment>/<run_id>/`에 전 산출물을 쓰고 INDEX를 갱신한다."""
    _validate(raw, cases)
    out = Path(results_root) / meta.experiment / meta.run_id
    out.mkdir(parents=True, exist_ok=True)

    meta_dict = meta.as_dict()
    (out / "meta.json").write_text(
        json.dumps(meta_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "cases.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    (out / "report.md").write_text(render_markdown(meta, raw), encoding="utf-8")
    (out / "report.html").write_text(render_html(meta, raw), encoding="utf-8")

    index = Path(results_root) / "INDEX.md"
    index.write_text(render_index(Path(results_root)), encoding="utf-8")
    return out


def _table(plans: Sequence[str], rows: Sequence[tuple[str, list]]) -> list[str]:
    out = ["| 항목 | " + " | ".join(plans) + " |",
           "|---|" + "---|" * len(plans)]
    for label, values in rows:
        cells = " | ".join(str(v) for v in values)
        out.append(f"| {label} | {cells} |")
    out.append("")
    return out


def _section(qa: str, data: dict, plans: Sequence[str]) -> list[str]:
    """QA 1종의 표. 지표별로 방안을 가로로 늘어놓는다."""
    keys: list[tuple[str, str]] = {
        "fc": [("mean_s", "개선 비율 s (판정)"), ("stars_s", "별점"),
               ("mean_achieved", "달성률 (수치 병기)"),
               ("mean_baseline", "무작위 베이스라인 R̄"),
               ("optimal_hit", "최적안 적중"), ("fr_violation_cases", "FR 위반 케이스"),
               ("degenerate_cases", "R̄=1 케이스 (s 판별력 없음)"),
               ("degenerate_missed", "그중 유효 후보 밖")],
        "cf": [("m", "노출 배수 m"), ("stars_m", "m 별점"),
               ("max_single_depth", "최대 단일 관찰자 깊이")],
        "tb": [("median_total_ms", "세션 시간 (ms)"), ("dominant", "지배 항"),
               ("median_phase_ms", "통신 항"), ("median_transfer_ms", "전송 항")],
        "ru": [("median_total_mb", "단말 총 점유 (MB)"), ("median_peak_mb", "프로토콜 상태 (MB)"),
               ("median_base_mb", "공통 기저 (MB)"), ("stars_median", "별점"),
               ("over_ceiling_sessions", "한도 초과 세션")],
        "sc_issue": [("max_issues", "최대 의제 수 (판정)"), ("stars_max_issues", "별점"),
                     ("censored", "censored (스윕 미도달)"),
                     ("c", "탄력성 c (보조)"), ("stars_c", "c 별점 (보조)"),
                     ("gate_ok", "완결률 게이트 (보조)")],
    }[qa]

    rows = []
    for key, label in keys:
        values, seen = [], False
        for p in plans:
            v = (data.get(p) or {}).get(key)
            if v is not None:
                seen = True
            values.append(stars(v) if key.startswith("stars") and isinstance(v, int)
                          else cell(v))
        if seen:
            rows.append((label, values))
    if not rows:
        return []

    out = [f"### {QA_TITLES[qa]}", ""] + _table(plans, rows)
    for note in _notes(qa, data, plans):
        out += [f"> {note}", ""]
    return out


def _notes(qa: str, data: dict, plans: Sequence[str]) -> list[str]:
    """수치만으로는 오독되는 지점을 표 아래에 붙인다."""
    notes: list[str] = []
    if qa == "fc" and any((data.get(p) or {}).get("mean_baseline") is not None
                          for p in plans):
        notes.append("개선 비율 s는 **표본 전체의 달성률 평균과 R̄ 평균으로 한 번 환산**한 "
                     "값이다 (24 §1.4 「집계 수준」) — 세션별 s의 평균이 아니므로 "
                     "케이스 표(`cases.jsonl`)의 `s` 열을 평균 내면 값이 다르다. "
                     "s = (달성률 − R̄) ÷ (1 − R̄)로 위 표에서 직접 검산할 수 있다")
    for p in plans:
        d = data.get(p) or {}
        if qa == "fc" and d.get("degenerate_missed"):
            notes.append(f"`{p}` **R̄=1 케이스 {d['degenerate_missed']}건에서 유효 후보 밖으로 "
                         f"합의했다** — 무작위조차 만점을 받는 판에서 놓친 것이므로 24 §1.4에 "
                         f"따라 해당 케이스의 s는 0점(즉시 결함)이다. 달성률 원값과 FR 위반 "
                         f"플래그를 함께 확인할 것")
        if qa == "cf" and d.get("m") is None and d.get("note"):
            notes.append(f"`{p}` m: {d['note']}")
        if qa == "sc_issue" and d.get("censored"):
            notes.append(f"`{p}` 최대 의제 수는 **하한**이다 — 스윕이 메모리 한도에 닿지 "
                         f"못해 실제 최대는 더 클 수 있다")
        if qa == "sc_issue" and d.get("defect"):
            notes.append(f"`{p}` **완결률 게이트 실패** — 규모가 커질수록 결렬이 늘어 "
                         f"탄력성이 좋아 보이는 왜곡이다 (24 §5.4). c 별점은 0으로 덮었다")
    return list(dict.fromkeys(notes))[:6]      # 순서 유지 중복 제거


def render_markdown(meta: RunMeta, raw: dict) -> str:
    m = meta.as_dict()
    plans = list(meta.plans)
    lines = [
        f"# {meta.experiment} — {meta.run_id}",
        "",
        f"- 생성: {m['created_at']} · 시드 {m['seed']} · commit `{m['commit']}` "
        f"· negmas {m['negmas']} · Python {m['python']}",
        f"- 데이터셋: `{m['dataset'].get('name')}` "
        f"(참여자 {m['dataset'].get('n_participants')} · 의제 {m['dataset'].get('n_issues')})",
        f"- 합성 시간 상수: t_phase {m['constants']['t_phase_ms']}ms(편도) · "
        f"t_eval {m['constants']['t_eval_ms']}ms · bw {m['constants']['bw_bytes_per_s']:,.0f} B/s",
        "",
        "> 별점 사다리 중 일부는 **잠정**이다 (24 §3.3 등). 별점만 보지 말고 원지표를 함께 읽어야 한다.",
        "",
    ]
    if m["note"]:
        lines += [f"> {m['note']}", ""]
    for qa in QA_KEYS:
        if qa in raw:
            lines += _section(qa, raw[qa], plans)
    return "\n".join(lines)


_HTML_HEAD = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:2rem auto;max-width:64rem;
padding:0 1rem;line-height:1.6;color:#1a1a1a}}
h1{{border-bottom:2px solid #ddd;padding-bottom:.3rem}}
h3{{margin-top:2rem;color:#333}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem}}
th,td{{border:1px solid #ddd;padding:.4rem .6rem;text-align:left}}
th{{background:#f5f5f5}}
blockquote{{border-left:4px solid #f0ad4e;background:#fffaf0;margin:1rem 0;padding:.5rem 1rem}}
code{{background:#f5f5f5;padding:.1rem .3rem;border-radius:3px}}
@media(prefers-color-scheme:dark){{body{{background:#161616;color:#e8e8e8}}
th{{background:#242424}}th,td{{border-color:#333}}code{{background:#242424}}
blockquote{{background:#2a2418;border-left-color:#a97c2c}}}}
</style>
"""


def render_html(meta: RunMeta, raw: dict) -> str:
    """마크다운을 최소 HTML로 옮긴다 — 외부 의존 없이 브라우저에서 바로 열리게."""
    md = render_markdown(meta, raw)
    body: list[str] = []
    in_table = False
    for line in md.split("\n"):
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue                       # 구분선
            tag = "th" if not in_table else "td"
            if not in_table:
                body.append("<table>")
                in_table = True
            body.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            body.append("</table>")
            in_table = False
        if line.startswith("# "):
            body.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("### "):
            body.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("> "):
            body.append(f"<blockquote>{line[2:]}</blockquote>")
        elif line.startswith("- "):
            body.append(f"<p>{line[2:]}</p>")
        elif line.strip():
            body.append(f"<p>{line}</p>")
    if in_table:
        body.append("</table>")
    return _HTML_HEAD.format(title=meta.run_id) + "\n".join(body)


def render_index(results_root: Path) -> str:
    """전 실행 요약 — 실험별로 묶고 최신순."""
    root = Path(results_root)
    rows = []
    for meta_path in root.glob("*/*/meta.json"):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append((m.get("run_id", meta_path.parent.name),
                     m.get("experiment", meta_path.parent.parent.name),
                     m.get("created_at", ""), m.get("commit"),
                     (m.get("dataset") or {}).get("name", "")))
    if not rows:
        return "# 측정 결과 INDEX\n\n_실행 없음_\n"

    rows.sort(key=lambda r: (r[0], r[2]), reverse=True)
    lines = ["# 측정 결과 INDEX", "",
             "| 실행 | 실험 | 생성 | commit | 데이터셋 | 리포트 |",
             "|---|---|---|---|---|---|"]
    for run_id, exp, created, commit, ds in rows:
        link = f"[md]({exp}/{run_id}/report.md) · [html]({exp}/{run_id}/report.html)"
        lines.append(f"| `{run_id}` | {exp} | {created} | `{commit}` | {ds} | {link} |")
    return "\n".join(lines) + "\n"
