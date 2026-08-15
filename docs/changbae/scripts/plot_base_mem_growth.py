# -*- coding: utf-8 -*-
"""base(full 전수 나열) 의제 수별 메모리 성장 — DP 배경 장표용 (2026-08-15).

실측: poc/dp-composite-agenda P5(oom_stress) — 6축 0.2MB · 8축 3.1MB · 10축 69MB
(S11 계열, 축당 값 5). 10축 초과는 실측 성장률(8→10축 ×22.3/2축 = 축당 ×4.7)
외삽 — 점선·빈 마커로 구분. 한도 128MB = 24 §2.8 (ART 힙 256MB×75% − 앱 기본 64MB).

사용: python docs/changbae/scripts/plot_base_mem_growth.py
출력: docs/changbae/figures/fig-base-mem-growth.png (300dpi)
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "figures", "fig-base-mem-growth.png")

BLUE = "#2a78d6"   # 계열 (dataviz 팔레트 slot 1)
RED = "#d03b3b"    # 한도선 (status critical)
INK_MUTED = "#898781"

CEIL = 128.0
GROWTH = 4.7                      # 축당 성장률 (8→10축 실측 22.26 ** 0.5)
MEAS_X, MEAS_Y = [6, 8, 10], [0.2, 3.1, 69.0]
EXT_X = [10, 11, 12]
EXT_Y = [69.0, 69.0 * GROWTH, 69.0 * GROWTH ** 2]   # 324 · 1,524MB

# 128MB 교차점: 69 * 4.7^t = 128  →  t = log(128/69)/log(4.7)
import math

CROSS_X = 10 + math.log(CEIL / 69.0) / math.log(GROWTH)   # ≈ 10.40

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(8.6, 4.8), dpi=300)

# 한도선
ax.axhline(CEIL, color=RED, linewidth=1.6, linestyle=(0, (6, 3)), zorder=1)
ax.text(5.62, CEIL + 38, "한도 128MB", color=RED, fontsize=13, va="bottom")

# 실측 구간 (실선·채운 마커)
ax.plot(MEAS_X, MEAS_Y, "-", color=BLUE, linewidth=2.6, zorder=3)
ax.plot(MEAS_X, MEAS_Y, "o", color=BLUE, markersize=8, zorder=4)
# 외삽 구간 (점선·빈 마커) — 모델 그대로의 지수 곡선 (직선 연결 시 교차점과 어긋남)
EXT_XS = [10 + i / 50.0 for i in range(101)]
EXT_YS = [69.0 * GROWTH ** (x - 10) for x in EXT_XS]
ax.plot(EXT_XS, EXT_YS, linestyle=(0, (4, 2.5)), color=BLUE, linewidth=2.2, zorder=3)
ax.plot(EXT_X[1:], EXT_Y[1:], "o", markerfacecolor="white", markeredgecolor=BLUE,
        markeredgewidth=1.8, markersize=8, zorder=4)

# 교차점 표식
ax.plot([CROSS_X], [CEIL], "o", color=RED, markersize=9, zorder=5,
        markerfacecolor=RED, markeredgecolor="white", markeredgewidth=1.6)

# 선택적 직접 라벨 3개
ax.annotate("69MB", (10, 69), textcoords="offset points", xytext=(6, -16),
            fontsize=12, color=BLUE)
ax.annotate("약 1.5GB", (12, EXT_Y[-1]), textcoords="offset points", xytext=(-4, 10),
            fontsize=13, color=BLUE, ha="right", fontweight="bold")

# 축 — y 눈금 표준형, x는 정수 축 수만
ax.set_xlim(5.6, 12.35)
ax.set_ylim(0, 1680)
ax.set_xticks([6, 8, 10, 12])
ax.set_yticks([0, 500, 1000, 1500])
ax.set_xlabel("의제 수", fontsize=12, color=INK_MUTED)
ax.set_ylabel("메모리 (MB)", fontsize=12, color=INK_MUTED)
ax.tick_params(labelsize=12, colors=INK_MUTED, length=4)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#c3c2b7")

# 외삽 주기 (근거 명시 — 최소 크기, 좌상단 여백)
ax.text(0.01, 0.97, "실측 6-10축(P5) · 10축 초과는 축당 ×4.7 외삽(점선)",
        transform=ax.transAxes, fontsize=8, color=INK_MUTED, ha="left", va="top")

# ── 인셋: 128MB 이하 구간 확대 ──────────────────────────────
# 7·9축은 실측이 없어 앞뒤 실측 비율의 기하 보간: 7축 ≈ 0.8 · 9축 ≈ 14.6MB
INTERP_X = [7, 9]
INTERP_Y = [math.sqrt(0.2 * 3.1), math.sqrt(3.1 * 69.0)]


def geo_seg(x0, y0, x1, y1, steps=30):
    xs = [x0 + (x1 - x0) * i / steps for i in range(steps + 1)]
    return xs, [y0 * (y1 / y0) ** ((x - x0) / (x1 - x0)) for x in xs]


axins = ax.inset_axes([0.07, 0.28, 0.40, 0.55])
axins.set_title("128MB 이하 확대 (7·9축 보간)", fontsize=9.5, color=INK_MUTED)
axins.axhline(CEIL, color=RED, linewidth=1.2, linestyle=(0, (6, 3)), zorder=1)
for x0, y0, x1, y1 in ((6, 0.2, 8, 3.1), (8, 3.1, 10, 69.0)):
    xs, ys = geo_seg(x0, y0, x1, y1)
    axins.plot(xs, ys, "-", color=BLUE, linewidth=2.2, zorder=3)
axins.plot(MEAS_X, MEAS_Y, "o", color=BLUE, markersize=6, zorder=4, linestyle="none")
axins.plot(INTERP_X, INTERP_Y, "o", markerfacecolor="white", markeredgecolor=BLUE,
           markeredgewidth=1.4, markersize=6, zorder=4, linestyle="none")
ins_xs = [x for x in EXT_XS if x <= CROSS_X]
axins.plot(ins_xs, [69.0 * GROWTH ** (x - 10) for x in ins_xs],
           linestyle=(0, (4, 2.5)), color=BLUE, linewidth=1.8, zorder=3)
axins.plot([CROSS_X], [CEIL], "o", markersize=7, zorder=5,
           markerfacecolor=RED, markeredgecolor="white", markeredgewidth=1.2)
for x, y, t, dx, ha in ((6, 0.2, "0.2", 0, "center"),
                        (7, INTERP_Y[0], "0.8", 0, "center"),
                        (8, 3.1, "3.1", 0, "center"),
                        (9, INTERP_Y[1], "14.6", -4, "center"),
                        (10, 69.0, "69", -8, "right")):
    axins.annotate(t, (x, y), textcoords="offset points", xytext=(dx, 7),
                   fontsize=10, color=BLUE, ha=ha)
axins.set_xlim(5.7, 10.75)
axins.set_ylim(0, 145)
axins.set_xticks([6, 7, 8, 9, 10])
axins.set_yticks([0, 50, 100, 128])
axins.set_yticklabels(["0", "50", "100", "128"])
axins.get_yticklabels()[-1].set_color(RED)
axins.tick_params(labelsize=9, colors=INK_MUTED, length=3)
for s in axins.spines.values():
    s.set_color("#c3c2b7")

fig.tight_layout()
fig.savefig(OUT, facecolor="white")
print("저장:", os.path.normpath(OUT), "· 교차점 x =", round(CROSS_X, 2))
