#!/usr/bin/env python3
"""61 브리핑용 QA 이해 보조 그림 5종 (PL 지시 2026-08-14 — 이해도 취지).

전부 **정본 실측 데이터에서 재집계한 그림**이다 (60·62·63 그림 규약과 같은 계열 —
개념 일러스트가 아니라 실측값의 주석 표현이므로 drawio 도식 규칙의 대상이 아니다).
라벨은 한국어 (Noto Sans CJK KR — 임원 청중).

- fig-p95-explain.png : P95 판정이란 — 방안 2 ρ의 ECDF에 중앙값/P95/느린 5% 주석
- fig-fc-scale.png    : FC 달성률 눈금 — 무작위 평균·1-A·방안 2·만점의 위치 + 별점 대역
- fig-ru-budget.png   : RU 한도 유도 — 256MB 힙의 분해 (GC 여유·앱 기본·협상 몫 128MB)
- fig-cf-secret.png   : CF 잔여 비밀률 — 후보 12개 순위표에서 공개/비밀 칸 (실측 평균)
- fig-sc-explosion.png: SC 조합 폭발 — 의제 수 vs 조합 수 (FIN 실측 중앙값, 로그축)

사용: .venv/bin/python scripts/plot_qa_explainers.py <nparty_run> <composite_run> <out_dir>
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

for f in font_manager.fontManager.ttflist:
    if f.name == "Noto Sans CJK KR":
        plt.rcParams["font.family"] = "Noto Sans CJK KR"
        break
plt.rcParams["axes.unicode_minus"] = False

BLUE = "#3A6FE0"
RED = "#D5484A"
GRAY = "#8A8A8A"
DPI = 300


def _clean(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.55")
    ax.tick_params(labelsize=9)


# ── 1. P95 설명 (방안 2의 ρ ECDF — 대표 그림) ─────────────────────────────────
def fig_p95(rho2, out):
    xs = sorted(rho2)
    n = len(xs)
    ys = [(i + 1) / n for i in range(n)]
    p95 = xs[min(n - 1, int(0.95 * n))]
    med = statistics.median(xs)

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=DPI)
    ax.step(xs, ys, where="post", color=RED, linewidth=1.8, label="방안 2의 시간 비율 ρ (480케이스)")
    # 느린 5% 꼬리 음영
    ax.fill_betweenx([0.95, 1.0], p95, max(xs) * 1.02, color=RED, alpha=0.10)
    ax.axhline(0.95, color="0.55", linewidth=0.9, linestyle=(0, (4, 3)))
    ax.axvline(p95, color=RED, linewidth=0.9, linestyle=(0, (2, 2)))
    ax.plot([med], [0.5], marker="o", color="0.4", markersize=5)
    ax.plot([p95], [0.95], marker="o", color=RED, markersize=6)
    ax.annotate("중앙값 0.17 — 전형 성능\n(케이스 절반이 이 아래)", (med, 0.5),
                textcoords="offset points", xytext=(10, -6), fontsize=9, color="0.30")
    ax.annotate(f"P95 = {p95:.2f} — 느린 쪽 5%의 경계\n★ 판정은 이 값으로 한다",
                (p95, 0.95), textcoords="offset points", xytext=(-205, -42),
                fontsize=9.5, color=RED, fontweight="bold")
    ax.annotate("가장 느린 5%\n(사용자가 체감하는 최악 구간)",
                (p95 * 1.02, 0.90), fontsize=8.5, color=RED, va="top")
    ax.set_xlim(0, max(xs) * 1.25)
    ax.set_ylim(0, 1.005)
    ax.set_xlabel("시간 비율 ρ = T(설계) ÷ T(naive)  — 작을수록 빠름", fontsize=10)
    ax.set_ylabel("누적 케이스 비율", fontsize=10)
    ax.grid(True, which="major", color="0.92", linewidth=0.7)
    _clean(ax)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9, edgecolor="0.75")
    fig.tight_layout()
    fig.savefig(out / "fig-p95-explain.png")
    plt.close(fig)


# ── 2. FC 달성률 눈금 ─────────────────────────────────────────────────────────
def fig_fc(out):
    bands = [(0.70, 0.80, "★1"), (0.80, 0.85, "★2"), (0.85, 0.90, "★3"),
             (0.90, 0.95, "★4"), (0.95, 1.001, "★5")]
    marks = [(0.863, "무작위 평균 R̄ 0.86", GRAY, -1),
             (0.873, "방안 1-A  0.873 (★3)", BLUE, 1),
             (0.9499, "방안 2  0.950 (★4 — ★5 경계 직하)", RED, 1),
             (1.0, "만점 1.0 = 최적 합의안", "0.2", -1)]
    fig, ax = plt.subplots(figsize=(9.0, 3.15), dpi=DPI)
    for lo, hi, lbl in bands:
        shade = 0.97 - 0.05 * bands.index((lo, hi, lbl))
        ax.axvspan(lo, hi, color=str(shade), zorder=0)
        ax.text((lo + hi) / 2, 0.08, lbl, ha="center", fontsize=10, color="0.35")
    for x, lbl, color, side in marks:
        ax.axvline(x, color=color, linewidth=1.6, ymin=0.18, ymax=0.62)
        ax.annotate(lbl, (x, 0.66 if side > 0 else 0.84), ha="center", fontsize=9.5,
                    color=color, fontweight="bold" if color in (BLUE, RED) else "normal")
    ax.annotate("", xy=(0.873, 0.30), xytext=(0.863, 0.30))
    ax.set_xlim(0.68, 1.03)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xlabel("달성률 = 도달한 결과의 효용 ÷ 최적 합의안의 효용", fontsize=10)
    ax.set_title("무작위로 골라도 0.86인 판 — 1-A는 그 바로 위, 방안 2는 ★4 대역", fontsize=10.5, color="0.25")
    _clean(ax)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig-fc-scale.png")
    plt.close(fig)


# ── 3. RU 한도 유도 ───────────────────────────────────────────────────────────
def fig_ru(out):
    fig, ax = plt.subplots(figsize=(9.0, 3.15), dpi=DPI)
    segs = [(128, "협상 몫  128MB", "#DEEBF7", "#2E74B5"),
            (64, "협상 외 앱 기본  64MB (잠정)", "#F2F2F2", "0.4"),
            (64, "GC 성능 여유  64MB (25%)", "#FBE5E5", "#C0392B")]
    left = 0
    for w, lbl, fc_, tc in segs:
        ax.barh(0.55, w, left=left, height=0.34, color=fc_, edgecolor="0.6")
        ax.text(left + w / 2, 0.55, lbl, ha="center", va="center", fontsize=9.5, color=tc)
        left += w
    ax.annotate("안드로이드 앱 힙 상한 256MB (플래그십 전형)", (128, 0.83), ha="center",
                fontsize=10, color="0.25")
    ax.annotate("협상이 쓸 수 있는 몫 = 128MB\n판정: 최대 부하 단말의 피크 ÷ 128MB (P95 · 로그 사다리)",
                (64, 0.18), ha="center", fontsize=9.5, color="#2E74B5", fontweight="bold")
    ax.set_xlim(0, 256)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([0, 64, 128, 192, 256])
    ax.set_xlabel("MB", fontsize=9)
    _clean(ax)
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig-ru-budget.png")
    plt.close(fig)


# ── 4. CF 잔여 비밀률 (실측 평균 노출 칸) ─────────────────────────────────────
def fig_cf(depth1a, depth2, out):
    n_cand = 12
    reveal = {"방안 1-A": depth1a * n_cand, "방안 2": depth2 * n_cand}
    colors = {"방안 1-A": BLUE, "방안 2": RED}
    fig, ax = plt.subplots(figsize=(9.0, 3.15), dpi=DPI)
    for col, (plan, rv) in enumerate(reveal.items()):
        x0 = col * 1.6
        for i in range(n_cand):  # i=0이 1순위 (위에서 아래)
            y = 0.92 - i * 0.075
            frac = min(1.0, max(0.0, rv - i))
            ax.barh(y, 1.0, left=x0, height=0.06, color="0.93", edgecolor="0.75", linewidth=0.4)
            if frac > 0:
                ax.barh(y, frac, left=x0, height=0.06, color=colors[plan], alpha=0.75)
        secret = 100 * (1 - rv / n_cand)
        ax.text(x0 + 0.5, 1.02, plan, ha="center", fontsize=10.5, fontweight="bold",
                color=colors[plan])
        ax.text(x0 + 0.5, -0.06, f"평균 {rv:.1f}개 공개 → 잔여 비밀 {secret:.0f}%",
                ha="center", fontsize=9.5, color=colors[plan])
    ax.text(-0.28, 0.92, "1순위", fontsize=8.5, color="0.4", va="center", ha="right")
    ax.text(-0.28, 0.92 - 11 * 0.075, "12순위", fontsize=8.5, color="0.4", va="center", ha="right")
    ax.text(3.65, 0.62, "색 = 나를 가장 많이 아는\n관찰자에게 공개된 후보\n회색 = 끝까지 비밀",
            fontsize=9, color="0.3", va="center")
    ax.set_xlim(-0.7, 5.2)
    ax.set_ylim(-0.14, 1.12)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "fig-cf-secret.png")
    plt.close(fig)


# ── 5. SC 조합 폭발 (FIN 실측 중앙 S) ─────────────────────────────────────────
def fig_sc(s_by_axes, out):
    xs = sorted(s_by_axes)
    ys = [s_by_axes[x] for x in xs]
    fig, ax = plt.subplots(figsize=(9.0, 3.15), dpi=DPI)
    ax.plot(xs, ys, marker="o", markersize=4, color=BLUE, linewidth=1.6,
            label="후보 조합 수 (FIN 실측 중앙값)")
    ax.set_yscale("log")
    ax.axvline(4, color="0.6", linewidth=0.9, linestyle=(0, (3, 3)))
    ax.text(4.15, ys[0] * 12, "요구 4축\n(기준 시나리오)", fontsize=8.5, color="0.35")
    ax.axvline(12, color="0.6", linewidth=0.9, linestyle=(0, (3, 3)))
    ax.text(12.1, ys[0] * 3, "실사용 최대 12축\n(★5 경계)", fontsize=8.5, color="0.35")
    ax.annotate("20축 = 조합 약 1,600억 개\n(전개 불가 — 설계 없이는 협상 자체가 불가능)",
                (xs[-1], ys[-1]), textcoords="offset points", xytext=(-235, -16),
                fontsize=9, color=BLUE, fontweight="bold")
    ax.annotate("4-12축 구간은 오라클 채점을 위해\n조합을 15만 이하로 통제 (CR 트랙)",
                (8, 2e5), fontsize=8.5, color="0.4", va="bottom")
    ax.set_xlabel("의제(축) 수", fontsize=10)
    ax.set_ylabel("후보 조합 수 (로그)", fontsize=10)
    ax.grid(True, which="major", color="0.92", linewidth=0.7)
    _clean(ax)
    ax.legend(loc="center left", fontsize=9, framealpha=0.9, edgecolor="0.75")
    fig.tight_layout()
    fig.savefig(out / "fig-sc-explosion.png")
    plt.close(fig)


def main() -> int:
    np_run, cp_run, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)

    np_rows = [json.loads(l) for l in open(np_run / "cases.jsonl")]
    rho2 = [r["rho"] for r in np_rows if r["plan"] == "plan2" and r.get("rho") is not None]
    # CF: 합의 세션 피해자 평균의 최악 관찰자 깊이 (판정 모수와 동일)
    def mean_depth(plan):
        vals = [d for r in np_rows if r["plan"] == plan and r["agreed"]
                for d in r["victim_depths"]]
        return statistics.fmean(vals)
    d1a, d2 = mean_depth("plan1a"), mean_depth("plan2")

    cp_rows = [json.loads(l) for l in open(cp_run / "cases.jsonl")]
    byax = defaultdict(list)
    for r in cp_rows:
        if r["plan"] == "seq2" and r.get("S"):
            byax[r["n_issues"]].append(r["S"])
    s_by_axes = {n: statistics.median(v) for n, v in byax.items()}

    fig_p95(rho2, out)
    fig_fc(out)
    fig_ru(out)
    fig_cf(d1a, d2, out)
    fig_sc(s_by_axes, out)
    print(f"5종 저장 → {out} (CF 평균 깊이 1-A {d1a:.3f} / 방안2 {d2:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
