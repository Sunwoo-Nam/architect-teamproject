"""의제 조합(issue space) 벤치마크 케이스 생성기 — `issue-space-case.v1`.

기존 `benchmark-case.v1`은 후보를 평면 문자열 목록(`S01`…`S12`)으로 펼쳐 저장한다.
그러나 실제 문제(영화 약속)의 후보는 **날짜 × 시간 × 영화관 × 영화의 곱**이고, 조합 수는
수천~수만 개다. 이것을 JSON에 전부 펼치면 케이스 하나가 수 MB가 되고, 파일을 읽는 순간
이미 `O(S)` 메모리를 쓰므로 "프로토콜이 전체 열거를 피하는가"를 측정할 수 없다
(01-테스트-케이스-확장-계획.md §8.3).

그래서 본 스키마는 **의제별 점수만 저장하고 조합은 실행 시 계산한다.**
조합이 10만 개여도 파일은 수 KB다.

    utility(조합) = Σ_j weights[issue_j] × scores[issue_j][value_j]

`weights` 합이 정확히 1이고 모든 `scores` 값이 [0,1]이므로 utility ∈ [0,1]이 구조적으로
보장된다 — 후보를 펼치지 않고도 값 범위를 증명할 수 있다는 것이 이 형식의 이점이다.

수락 기준값(`initial_threshold`)은 **계산해서 정한다.** 의제가 많아질수록 utility가
평균 근처로 몰려서, 기준값을 눈대중으로 고르면 대부분의 케이스가 "전부 통과" 아니면
"전부 결렬"이 된다 — 어느 쪽이든 방안을 구분하지 못한다. 전원 수락 가능한 조합이
목표 비율이 되는 기준값을 조합을 실제로 세어 정한다 (solve_thresholds).

로더 의존 없음: `src/dp2_nparty/benchmark.py`의 `validate_case`는 `benchmark-case.v1`
전용이고 스키마가 다르다. 또한 `issue-space-case.v1` 로더는 현재 별도 작업 중이므로,
본 생성기는 검증을 **스크립트 안에서 자체적으로** 수행한다.

사용:
    .venv/bin/python scripts/generate_issue_space.py                # 4단계 × 2종 × 10건 = 80건
    .venv/bin/python scripts/generate_issue_space.py --per-config 2 # 축소 (단계·인원당 2건)
    .venv/bin/python scripts/generate_issue_space.py --steps 1 2    # 의제 4·6개만
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import time
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "cases" / "issue-space"

SCHEMA_VERSION = "issue-space-case.v1"
TRACK = "issue_space"
SCENARIO_TYPE = "movie_appointment"

# --- 의제 정의 -----------------------------------------------------------------
#
# 의제 수를 4 → 10으로 늘리면서 조합 수는 비슷하게 유지한다 (아래 ISSUE_LEVELS).
#
# 값 풀에서 **앞에서부터 잘라** 쓴다 — 단계가 올라가도 작은 단계의 값이 그대로 남고 새 값만
# 추가되므로, 단계 사이 차이에 '문제가 통째로 바뀐 효과'가 섞이지 않는다
# (`generate_scalability.py`의 family 구성과 같은 이유).

DATE_ORIGIN = date(2026, 11, 15)
DATE_POOL = [(DATE_ORIGIN + timedelta(days=i)).strftime("%m-%d") for i in range(25)]
# 30분 간격 상영 시간 12:00 ~ 21:30 (20개)
TIME_POOL = [f"{12 + i // 2}:{'00' if i % 2 == 0 else '30'}" for i in range(20)]
VENUE_POOL = ["강남", "홍대", "잠실", "왕십리", "용산", "영등포", "신촌", "건대입구", "목동", "코엑스"]
# 실존 작품과의 혼동을 피하려고 가상의 제목을 쓴다 (AGENTS.md: 출처를 추측해 기록하지 않는다)
MOVIE_POOL = [
    "겨울 항해", "붉은 사막", "야간비행", "종이 도시", "여덟 번째 계절",
    "파란 문", "먼 북소리", "은하 정거장", "조용한 이웃", "마지막 정류장",
    "빛의 속도로", "검은 숲", "유리 정원", "새벽 세 시", "천 개의 파도",
    "우연한 여행자", "달의 뒷면", "낮은 목소리", "회색 항구", "봄의 알고리즘",
]

SEAT_POOL = ["일반", "프리미엄", "리클라이너", "커플석"]
FORMAT_POOL = ["2D", "3D", "IMAX", "4DX"]
MEAL_POOL = ["관람 전 식사", "관람 후 식사", "간식만", "식사 없음"]
TRANSPORT_POOL = ["지하철", "버스", "자차", "택시"]
BUDGET_POOL = ["1만원대", "1만5천원대", "2만원대", "2만5천원대"]
AFTER_POOL = ["바로 귀가", "카페", "가벼운 술자리", "산책"]

# (의제 id, 표시 이름, 값 풀) — 순서가 곧 조합 튜플의 자리 순서다.
# 앞 4개는 약속의 뼈대이고, 뒤 6개는 의제 수를 10개까지 늘릴 때 덧붙이는 항목이다.
ISSUE_DEFS = (
    ("date", "날짜", DATE_POOL),
    ("time", "시간", TIME_POOL),
    ("venue", "영화관", VENUE_POOL),
    ("movie", "영화", MOVIE_POOL),
    ("seat", "좌석", SEAT_POOL),
    ("format", "상영 형식", FORMAT_POOL),
    ("meal", "식사", MEAL_POOL),
    ("transport", "이동", TRANSPORT_POOL),
    ("budget", "예산", BUDGET_POOL),
    ("after", "관람 후", AFTER_POOL),
)

# 2026-08-12 축소 개정: 참여자 20명·조합 10만대 4형태는 실측 결과 순차형 방안(14개 중 11개)의
# 라운드 수가 케이스당 수만 회에 달해(조합 62,208·참여자 10명에서 방안2 실측 34,256라운드·
# 10.4초) 방안 2개만으로도 전체 실행이 3.5~7시간으로 추산됐다. 참여자를 10명으로 고정하고
# 같은 의제 목록을 앞에서부터 잘라 3단계(d=3/6/10)로 줄인다 — d=10(62,208)은 기존 형태를
# 그대로 유지해 이전 실측과 비교 가능하게 하고, d=6·d=3은 그 앞부분만 잘라 조합을 1,728·64로
# 낮춰 "차이가 언제부터 벌어지는지"를 보게 한다.
ISSUE_LEVELS = (
    (4, 4, 4),                              # d=3  →      64
    (4, 4, 4, 3, 3, 3),                     # d=6  →   1,728
    (4, 4, 4, 3, 3, 3, 3, 3, 2, 2),         # d=10 →  62,208 (기존 형태 유지)
)

PARTICIPANT_COUNTS = (10,)
PER_CONFIG = 10  # (의제 수 단계 × 참여자 수)당 케이스 수 → 3 × 1 × 10 = 30건/트랙

# 수락 기준값은 **계산해서 정한다.**
#
# 눈대중으로 고를 수 없는 이유: utility가 의제별 점수의 가중평균이라 의제가 많아질수록
# 값이 평균(0.5) 근처로 몰린다 — 참여자 1인의 utility 표준편차가 의제 2개에서 0.287,
# 10개에서 0.087이다. 그래서 의제 10개에서는 기준값 0.45와 0.48 사이(0.03 차이)에서
# 전원 수락 가능한 조합이 303개에서 46개로 바뀐다. 고정 대역을 뿌리면 대부분의 케이스가
# "전부 통과" 아니면 "전부 결렬"이 되어 측정이 성립하지 않는다.
#
# 목표 비율의 근거: 전원 수락 가능한 조합의 비율이 3% 이상이면 메모리가 부족해 일부만
# 검토해도 좋은 안을 쉽게 찾아 방안 간 차이가 사라지고, 0.05% 이하면 양쪽 다 결렬해서
# 역시 차이가 사라진다. 0.3~1.0% 구간에서만 방안이 구분된다 (사전 검증 실측).
# 트랙별 목표 비율 — 두 측정이 서로 반대되는 난이도를 요구하므로 케이스를 나눈다.
#   A 트랙(0.5%): 합의안이 각자 순위표의 깊은 곳에 있어, 메모리가 부족해 일부만 검토하면
#       좋은 안을 놓친다 → **정확도**가 갈린다. 대신 점진형도 거의 전 조합을 훑게 되어
#       담당자 보유량이 일괄형과 같아지므로 메모리는 갈리지 않는다 (실측 확인).
#   B 트랙(5%): 합의안이 얕아 점진형이 일찍 멈춘다 → **단말 1대의 보유량**이 갈린다.
#       대신 좁게 검토해도 쉽게 찾으므로 정확도는 갈리지 않는다.
TRACK_RATIOS = {"a": 0.005, "b": 0.05}
FEASIBLE_RATIO_TARGET = TRACK_RATIOS["a"]  # 기본값 (--track 으로 바꾼다)
THRESHOLD_JITTER = 0.03  # 참여자마다 기준값을 조금씩 다르게 (전원 같은 값이면 비현실적)
MIN_WEIGHT = 0.08  # 가중치가 0에 가까우면 그 의제가 사실상 사라져 조합 구조가 무너진다

TOL = 1e-9
CROSS_CHECK_MAX = 2000  # 이 크기 이하에서는 정의 그대로의 이중 계산으로 교차 확인한다


# --- 케이스 구성 ---------------------------------------------------------------

def build_issues(sizes: tuple[int, ...]) -> list[dict]:
    """의제별 값 개수를 받아 의제 목록을 만든다.

    의제는 `ISSUE_DEFS`의 앞에서부터 `len(sizes)`개를 쓰고, 각 의제의 값도 값 풀의
    앞에서부터 자른다 — 의제 수가 늘어도 앞 단계의 의제·값이 그대로 남으므로,
    단계 사이 차이에 '문제가 통째로 바뀐 효과'가 섞이지 않는다.
    """
    if not 1 <= len(sizes) <= len(ISSUE_DEFS):
        raise SystemExit(f"의제 개수는 1~{len(ISSUE_DEFS)}개여야 한다 (받은 값: {len(sizes)}개)")
    issues = []
    for (iid, name, pool), k in zip(ISSUE_DEFS[: len(sizes)], sizes):
        if not 1 <= k <= len(pool):
            raise SystemExit(f"의제 '{iid}'의 값 개수 {k}는 값 풀 크기 {len(pool)}를 벗어난다")
        issues.append({"id": iid, "name": name, "values": list(pool[:k])})
    return issues


def build_participant(pid: str, issues: list[dict], rng: random.Random, shift: float) -> dict:
    """참여자 1명 — 의제 가중치(합 1)와 의제 값별 점수를 무작위로 만든다."""
    # 가중치: 균등 난수를 정규화한다. 한 의제가 사실상 무시되지 않도록 하한을 두고 재시도한다.
    while True:
        raw = [rng.random() + 0.05 for _ in issues]
        total = sum(raw)
        w = [v / total for v in raw]
        if min(w) >= MIN_WEIGHT:
            break
    # 합을 정확히 1로 맞춘다 — 마지막 의제에 반올림 잔차를 몰아준다(최대 1.5e-4로 무시 가능).
    rounded = [round(v, 4) for v in w[:-1]]
    rounded.append(round(1.0 - sum(rounded), 4))

    weights = {issue["id"]: rounded[j] for j, issue in enumerate(issues)}
    scores = {
        issue["id"]: {v: round(rng.random(), 4) for v in issue["values"]}
        for issue in issues
    }
    # initial_threshold 는 여기서 정하지 않는다 — 전 조합의 utility를 계산한 뒤
    # solve_thresholds() 가 목표 비율에 맞춰 채운다.
    return {
        "pid": pid,
        "initial_threshold": None,
        "weights": weights,
        "scores": scores,
        "_offset": round(rng.uniform(-THRESHOLD_JITTER, THRESHOLD_JITTER), 4),
    }


def solve_thresholds(issues: list[dict], participants: list[dict], rng: random.Random,
                     target_ratio: float = FEASIBLE_RATIO_TARGET) -> int:
    """전원 수락 가능한 조합이 목표 비율이 되도록 참여자별 수락 기준값을 정한다.

    참여자 i의 기준값을 `t + offset_i` 로 두면(offset은 사람마다 다른 고정 지터),
    조합 c를 전원이 수락할 조건은 `모든 i에 대해 u_i(c) ≥ t + offset_i`,
    즉 `min_i (u_i(c) − offset_i) ≥ t` 이다. 그래서 조합마다 이 최솟값을 한 번 구해
    내림차순 정렬해 두면, 목표 개수 k번째 값이 곧 정답 t다 — 탐색이 필요 없다.

    반환: 실제로 전원 수락 가능해진 조합 수.
    """
    grids = [utility_grid(issues, p) for p in participants]
    offs = [p["_offset"] for p in participants]
    margins = sorted(
        (min(u - o for u, o in zip(vals, offs)) for vals in zip(*grids)), reverse=True
    )
    total = len(margins)
    k = max(1, min(total, round(total * target_ratio)))
    # k번째로 큰 값을 기준으로 잡으면 정확히 k개가 통과한다. 3자리로 반올림하면 경계가
    # 움직일 수 있으므로, 내림(더 관대한 쪽)해서 목표보다 적어지지 않게 한다.
    t = math.floor(margins[k - 1] * 1000) / 1000
    for p, o in zip(participants, offs):
        p["initial_threshold"] = round(min(1.0, max(0.0, t + o)), 4)
        del p["_offset"]
    # 반올림·클램프 이후의 실제 개수를 다시 센다 (기록되는 값은 이것이다)
    ths = [p["initial_threshold"] for p in participants]
    return sum(1 for vals in zip(*grids) if all(u >= th for u, th in zip(vals, ths)))


def utility_grid(issues: list[dict], participant: dict) -> list[float]:
    """전 조합의 utility — 의제별 `weights×scores` 기여도 표를 누적 합성한다.

    S = 10만이면 조합을 튜플로 만들어 매번 합하는 방식은 참여자당 10만 번의 튜플 생성이다.
    여기서는 의제를 하나씩 붙이며 부분합만 늘리므로 튜플을 만들지 않는다.
    산출 순서는 `itertools.product(*values)`와 같다 — 마지막 의제가 가장 빨리 변한다.
    """
    acc = [0.0]
    for issue in issues:
        w = participant["weights"][issue["id"]]
        table = participant["scores"][issue["id"]]
        contrib = [w * table[v] for v in issue["values"]]
        acc = [a + c for a in acc for c in contrib]
    return acc


def analyse(issues: list[dict], participants: list[dict]) -> tuple[int, float, float]:
    """(공통 실후보 수, 전 조합 utility 최솟값, 최댓값).

    공통 실후보 = 모든 참여자의 utility가 자기 `initial_threshold` 이상인 조합.
    참여자를 하나씩 걸러 생존 인덱스만 남기므로 교집합에 O(S×P) 메모리를 쓰지 않는다.
    """
    alive: list[int] | None = None
    umin, umax = 1.0, 0.0
    for p in participants:
        grid = utility_grid(issues, p)
        umin = min(umin, min(grid))
        umax = max(umax, max(grid))
        th = p["initial_threshold"]
        if alive is None:
            alive = [i for i, u in enumerate(grid) if u >= th]
        else:
            alive = [i for i in alive if grid[i] >= th]
    return len(alive or []), umin, umax


def build_case(case_id: str, sizes: tuple[int, ...], n_part: int,
               rng: random.Random, shift: float, target_ratio: float = FEASIBLE_RATIO_TARGET,
               track: str = 'a') -> dict:
    issues = build_issues(sizes)
    participants = [build_participant(f"P{j}", issues, rng, shift) for j in range(n_part)]
    combos = 1
    for issue in issues:
        combos *= len(issue["values"])
    feasible_n = solve_thresholds(issues, participants, rng, target_ratio)
    ratio = feasible_n / combos
    lo, hi = target_ratio * 0.6, target_ratio * 2.0
    # 조합 수가 적으면 목표 비율 자체가 정수 개수로 안 떨어질 수 있다
    # (예: 조합 64개에서 0.5%는 0.32건 — 애초에 불가능하다). 그런 경우 개수 기준으로
    # 밴드를 넓힌다. 조합이 충분히 크면 count_lo/count_hi가 비율 밴드보다 좁아 영향이 없다.
    k_target = max(1, round(combos * target_ratio))
    count_lo = max(1, k_target // 2) / combos
    count_hi = max(k_target * 3, k_target + 2) / combos
    lo, hi = min(lo, count_lo), max(hi, count_hi)
    if not (lo <= ratio <= hi):
        raise SystemExit(
            f"{case_id}: 전원 수락 가능한 조합 비율 {ratio:.4%} 가 목표 구간 "
            f"{lo:.1%}~{hi:.1%} 를 벗어났다 ({feasible_n}/{combos})"
        )
    shape = " × ".join(f"{i['name']} {len(i['values'])}" for i in issues)
    return {
        "case_id": case_id,
        "issues": issues,
        "participants": participants,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "track": TRACK,
            "scenario_type": SCENARIO_TYPE,
            "combination_count": combos,
            "issue_sizes": [len(i["values"]) for i in issues],
            "common_feasible_count": feasible_n,
            "expected_no_deal": feasible_n == 0,
            "tags": [f"track:{track}", f"issues:{len(issues)}",
                     f"participants:{n_part}", f"feasible_ratio:{ratio:.4f}"],
            "description": (
                f"영화 약속 {n_part}인 사례 — 의제 {len(issues)}개({shape}) = 조합 {combos:,}개. "
                "후보는 의제 값의 곱이며 utility는 의제 가중합으로 실행 시 계산한다. "
                f"전원의 initial threshold를 넘는 공통 실후보는 {feasible_n:,}개다."
            ),
        },
    }


# --- 자체 검증 -----------------------------------------------------------------

def validate_case(raw: dict, source: str) -> list[str]:
    """생성 결과가 스키마와 계산 규칙을 지키는지 **독립적으로** 다시 계산해 확인한다.

    생성 경로(`utility_grid`)는 누적 합성이고 여기서는 `itertools.product`로 조합을 직접
    만들어 합한다 — 같은 코드를 두 번 부르면 검증이 아니므로 계산 경로를 일부러 다르게 썼다.
    로더가 아직 작업 중이므로 외부 검증기에 의존하지 않는다.
    """
    e: list[str] = []
    meta = raw.get("meta", {})
    if meta.get("schema_version") != SCHEMA_VERSION:
        e.append(f"{source}: meta.schema_version 은 '{SCHEMA_VERSION}' 이어야 한다")
    if meta.get("track") != TRACK:
        e.append(f"{source}: meta.track 은 '{TRACK}' 이어야 한다")
    for key in ("scenario_type", "combination_count", "issue_sizes",
                "common_feasible_count", "expected_no_deal", "description"):
        if key not in meta:
            e.append(f"{source}: meta.{key} 가 없다")

    issues = raw.get("issues") or []
    if not issues:
        e.append(f"{source}: issues 가 비어 있다")
    ids = [i["id"] for i in issues]
    if len(set(ids)) != len(ids):
        e.append(f"{source}: 의제 id가 중복이다 — {ids}")
    for issue in issues:
        vals = issue.get("values") or []
        if not vals:
            e.append(f"{source}: 의제 '{issue.get('id')}'의 values 가 비어 있다")
        if len(set(vals)) != len(vals):
            e.append(f"{source}: 의제 '{issue['id']}'의 값이 중복이다")

    combos = 1
    for issue in issues:
        combos *= len(issue["values"])
    if meta.get("combination_count") != combos:
        e.append(f"{source}: combination_count {meta.get('combination_count')} ≠ 실제 곱 {combos}")
    if meta.get("issue_sizes") != [len(i["values"]) for i in issues]:
        e.append(f"{source}: issue_sizes 가 의제별 값 개수와 다르다")

    parts = raw.get("participants") or []
    if len(parts) < 3:
        e.append(f"{source}: 참여자는 3명 이상이어야 한다 (현재 {len(parts)}명)")
    pids = [p["pid"] for p in parts]
    if len(set(pids)) != len(pids):
        e.append(f"{source}: 참여자 id가 중복이다 — {pids}")

    for p in parts:
        pid = p.get("pid")
        th = p.get("initial_threshold")
        if not isinstance(th, (int, float)) or not 0.0 <= th <= 1.0:
            e.append(f"{source}/{pid}: initial_threshold 가 [0,1]을 벗어난다 — {th}")
        w = p.get("weights") or {}
        if sorted(w) != sorted(ids):
            e.append(f"{source}/{pid}: weights 키가 의제 id 목록과 다르다")
        else:
            wsum = sum(w[i] for i in ids)
            if abs(wsum - 1.0) > TOL:
                e.append(f"{source}/{pid}: weights 합이 1이 아니다 — {wsum!r}")
            if any(w[i] < 0 for i in ids):
                e.append(f"{source}/{pid}: 음수 가중치가 있다")
        sc = p.get("scores") or {}
        if sorted(sc) != sorted(ids):
            e.append(f"{source}/{pid}: scores 키가 의제 id 목록과 다르다")
            continue
        for issue in issues:
            table = sc[issue["id"]]
            if sorted(table) != sorted(issue["values"]):
                e.append(f"{source}/{pid}: scores['{issue['id']}'] 키가 해당 의제 values 와 다르다")
            elif any(not 0.0 <= v <= 1.0 for v in table.values()):
                e.append(f"{source}/{pid}: scores['{issue['id']}'] 에 [0,1] 밖 값이 있다")
    if e:
        return e  # 아래 전개 계산은 위 계약이 성립할 때만 의미가 있다

    # 전 조합 전개 — utility 범위와 공통 실후보 수를 정의 그대로 다시 센다
    alive: list[int] | None = None
    for p in parts:
        tables = [
            [p["weights"][issue["id"]] * p["scores"][issue["id"]][v] for v in issue["values"]]
            for issue in issues
        ]
        grid = [sum(t) for t in itertools.product(*tables)]
        if len(grid) != combos:
            e.append(f"{source}/{p['pid']}: 전개된 조합 수 {len(grid)} ≠ {combos}")
        if min(grid) < -TOL or max(grid) > 1.0 + TOL:
            e.append(f"{source}/{p['pid']}: utility 가 [0,1]을 벗어난다 "
                     f"— [{min(grid):.6f}, {max(grid):.6f}]")
        th = p["initial_threshold"]
        if alive is None:
            alive = [i for i, u in enumerate(grid) if u >= th]
        else:
            alive = [i for i in alive if grid[i] >= th]
    n_feasible = len(alive or [])
    if meta.get("common_feasible_count") != n_feasible:
        e.append(f"{source}: common_feasible_count {meta.get('common_feasible_count')} "
                 f"≠ 실제 {n_feasible}")
    if meta.get("expected_no_deal") != (n_feasible == 0):
        e.append(f"{source}: expected_no_deal 이 실제 계산({n_feasible == 0})과 다르다")

    # 작은 케이스는 값 조회 경로까지 정의 그대로 한 번 더 확인한다 (기여도 표 자체의 검산)
    if combos <= CROSS_CHECK_MAX:
        value_lists = [issue["values"] for issue in issues]
        for p in parts:
            for combo in itertools.product(*value_lists):
                u = sum(p["weights"][issues[j]["id"]] * p["scores"][issues[j]["id"]][v]
                        for j, v in enumerate(combo))
                if u < -TOL or u > 1.0 + TOL:
                    e.append(f"{source}/{p['pid']}: 조합 {combo} 의 utility {u} 가 [0,1] 밖이다")
                    break
    return e


# --- 생성 ----------------------------------------------------------------------

def _case_id(n_part: int, combos: int, seq: int, track: str = "a") -> str:
    """정렬했을 때 참여자 수 → 조합 수 → 일련번호 순으로 늘어서도록 자리수를 맞춘다."""
    suffix = "" if track == "a" else track.upper()
    return f"I{suffix}-{n_part:02d}p-S{combos:06d}-{seq:03d}"


def _build_all(steps: tuple[int, ...], participant_counts: tuple[int, ...],
               per_config: int, rng: random.Random, start: int, shift: float,
               target_ratio: float, track: str) -> list[dict]:
    cases = []
    for step in steps:
        sizes = ISSUE_LEVELS[step - 1]
        combos = 1
        for k in sizes:
            combos *= k
        for n_part in participant_counts:
            for i in range(per_config):
                case_id = _case_id(n_part, combos, start + i, track)
                cases.append(build_case(case_id, sizes, n_part, rng, shift, target_ratio, track))
    return cases


def generate(steps: tuple[int, ...], participant_counts: tuple[int, ...], per_config: int,
             seed: int, start: int, out_dir: Path, max_retry: int = 4,
             target_ratio: float = FEASIBLE_RATIO_TARGET, track: str = 'a') -> tuple[list[Path], float]:
    """케이스를 만들고 결렬 비율을 확인한 뒤 파일로 쓴다.

    전 케이스가 결렬(공통 실후보 0개)로만 채워지면 표본이 쓸모없다. 결렬이 절반을 넘으면
    수락 기준값 대역을 0.05씩 낮춰 다시 생성한다 — 개별 케이스를 골라내는 것이 아니라
    표본 전체를 같은 규칙으로 다시 만든다(선택 편향 방지).
    """
    shift = 0.0
    cases: list[dict] = []
    for attempt in range(max_retry + 1):
        rng = random.Random(seed + attempt)
        cases = _build_all(steps, participant_counts, per_config, rng, start, shift, target_ratio, track)
        zero = sum(1 for c in cases if c["meta"]["expected_no_deal"])
        print(f"  시도 {attempt + 1}: 기준값 보정 {shift:+.2f} → 결렬 {zero}/{len(cases)}건 "
              f"({zero / len(cases):.1%})")
        if zero * 2 <= len(cases):
            break
        shift -= 0.05
    else:
        raise SystemExit(f"수락 기준값을 {shift:+.2f}까지 낮춰도 결렬 케이스가 절반을 넘는다")

    errors: list[str] = []
    for raw in cases:
        errors += validate_case(raw, raw["case_id"])
    if errors:
        raise SystemExit("생성기가 계약을 어겼다:\n" + "\n".join(errors[:40]))

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for raw in cases:
        path = out_dir / f"{raw['case_id']}.json"
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written, shift


def _report(cases_meta: list[tuple[int, int, int]]) -> None:
    """(참여자 수, 조합 수, 공통 실후보 수) 목록에서 분포표를 출력한다."""
    print("\n  공통 실후보 수 분포")
    print(f"    {'참여자':>6} {'조합 S':>9} {'건수':>4} {'결렬':>4} {'최소':>6} {'중앙':>8} {'최대':>8}")
    keys = sorted({(n, s) for n, s, _ in cases_meta})
    for n, s in keys:
        vals = sorted(f for nn, ss, f in cases_meta if (nn, ss) == (n, s))
        mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        zero = sum(1 for v in vals if v == 0)
        print(f"    {n:>5}인 {s:>9,} {len(vals):>4} {zero:>4} {vals[0]:>6,} {mid:>8,.1f} {vals[-1]:>8,}")
    total_zero = sum(1 for _, _, f in cases_meta if f == 0)
    print(f"    전체 {len(cases_meta)}건 중 결렬 {total_zero}건 ({total_zero / len(cases_meta):.1%})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--participants", type=int, nargs="+", default=list(PARTICIPANT_COUNTS),
                    help="참여자 수 (기본: 3 10)")
    ap.add_argument("--per-config", type=int, default=PER_CONFIG,
                    help="(S 단계 × 참여자 수) 조합당 케이스 수 (기본: 10)")
    ap.add_argument("--steps", type=int, nargs="+", default=list(range(1, len(ISSUE_LEVELS) + 1)),
                    help=f"생성할 S 단계 번호 1..{len(ISSUE_LEVELS)} (기본: 전체)")
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--start", type=int, default=1, help="case_id 일련번호 시작값")
    ap.add_argument("--track", choices=sorted(TRACK_RATIOS), default="a",
                    help="a=정확도 판별용(실후보 0.5%%) · b=단말 부담 판별용(5%%)")
    ap.add_argument("--out", type=Path, default=None,
                    help="생략 시 트랙에 맞는 폴더 (issue-space / issue-space-b)")
    args = ap.parse_args()

    steps = tuple(args.steps)
    target_ratio = TRACK_RATIOS[args.track]
    out_dir = args.out or (OUT_DIR if args.track == "a" else OUT_DIR.with_name(f"issue-space-{args.track}"))
    print(f"  트랙 {args.track.upper()} — 전원 수락 가능한 조합 목표 비율 {target_ratio:.1%}")
    for s in steps:
        if not 1 <= s <= len(ISSUE_LEVELS):
            raise SystemExit(f"--steps 는 1..{len(ISSUE_LEVELS)} 범위여야 한다 (받은 값: {s})")

    print("  단계별 의제 구성 — 의제 수를 늘리되 조합 수는 비슷하게 유지한다")
    print(f"    {'단계':>4} {'의제 수':>6} {'조합 S':>9}  의제별 값 개수")
    for s in steps:
        sizes = ISSUE_LEVELS[s - 1]
        combos = 1
        for k in sizes:
            combos *= k
        names = " × ".join(f"{ISSUE_DEFS[j][1]} {k}" for j, k in enumerate(sizes))
        print(f"    {s:>4} {len(sizes):>6} {combos:>9,}  {names}")

    t0 = time.perf_counter()
    written, shift = generate(steps, tuple(args.participants), args.per_config,
                              args.seed, args.start, out_dir,
                              target_ratio=target_ratio, track=args.track)
    elapsed = time.perf_counter() - t0

    total_kb = sum(p.stat().st_size for p in written) / 1024
    cases_meta = []
    for p in written:
        raw = json.loads(p.read_text(encoding="utf-8"))
        cases_meta.append((len(raw["participants"]), raw["meta"]["combination_count"],
                           raw["meta"]["common_feasible_count"]))
    _report(cases_meta)

    print(f"\n  {len(written)}건 생성 ({total_kb:.1f} KB, {elapsed:.1f}초) → {out_dir}")
    print(f"  자체 검증 통과 — 전 케이스 weights 합·scores 범위·조합 수·utility 범위·"
          f"공통 실후보 수 재계산 일치 (기준값 보정 {shift:+.2f})")


if __name__ == "__main__":
    main()
