"""[24 §4] TB baseline (nparty) — naive 다자 SAOP(round-robin)의 T (PL 확정 2026-08-13).

가장 단순한 NegMAS식 다자 확장: 전 후보를 세워놓고, **1명씩 돌아가며** 자기 순위
다음 후보 1개를 전원에게 배포하고 전원이 accept/reject 회신한다. 전원 accept면 합의.
라운드당 제안이 1건뿐이라는 점이 우리 설계(전원 병렬 제출)와의 차이의 원천이다.

- 계수: 제안 1건 = 배포 N−1건(1 phase) + 회신 N−1건(1 phase). 성립 시 통지 1 phase.
- eval = N×S (naive 정의: 전 조합 순위화) + 회신 평가 (N−1)×k*.
- threshold·바퀴 tactic은 설계와 동일 (PolyAspiration boulware · [initial, own_max] ·
  최대 5바퀴, 바퀴마다 포인터 리셋). 결정론.
- nparty 후보 공간은 명시 목록(수십-수백)이라 lazy 탐색 없이 직접 정렬로 충분하다.
"""
from __future__ import annotations

from negmas.negotiators.helpers import PolyAspiration

from ...qa.constants import SYNTH_TIME

MAX_SWEEPS = 5


def baseline_t(profiles, candidates) -> dict:
    """naive SAOP-RR의 합성 시간. profiles는 계약 Profile(utility/ranked/initial_threshold)."""
    n = len(profiles)
    asp = PolyAspiration(max_aspiration=1.0, aspiration_type="boulware")
    ranked = [list(p.ranked()) for p in profiles]
    own_max = [p.utility(r[0]) if r else p.initial_threshold
               for p, r in zip(profiles, ranked)]

    def th(i, sweep):
        if MAX_SWEEPS <= 1:
            return profiles[i].initial_threshold
        t = min(1.0, max(0.0, (sweep - 1) / (MAX_SWEEPS - 1)))
        frac = asp.utility_at(t)
        init = profiles[i].initial_threshold
        return max(init, init + (own_max[i] - init) * frac)

    proposals = 0
    agreed = None
    bytes_total = 0
    for sweep in range(1, MAX_SWEEPS + 1):
        ptr = [0] * n
        exhausted = [False] * n
        turn = 0
        while not all(exhausted):
            i = turn % n
            turn += 1
            if exhausted[i]:
                continue
            if ptr[i] >= len(ranked[i]):
                exhausted[i] = True
                continue
            c = ranked[i][ptr[i]]
            if profiles[i].utility(c) < th(i, sweep):
                exhausted[i] = True  # 내림차순 — 이 바퀴 소진
                continue
            ptr[i] += 1
            proposals += 1
            bytes_total += (n - 1) * (len(str(c)) + 16) + (n - 1) * 8  # 배포 + O/X 회신
            if all(profiles[j].utility(c) >= th(j, sweep) for j in range(n) if j != i):
                agreed = c
                break
        if agreed is not None:
            break

    S = len(candidates)
    c_ = SYNTH_TIME
    phases = 2 * proposals + (1 if agreed is not None else 0)
    messages = 2 * (n - 1) * proposals + (n - 1 if agreed is not None else 0)
    eval_calls = n * S + (n - 1) * proposals
    t_phase = phases * c_.t_phase_ms
    t_eval = eval_calls / n * c_.t_eval_ms
    t_transfer = bytes_total / c_.bw_bytes_per_s * 1000
    return {
        "S": S, "n": n, "agreed": agreed is not None, "capped": False,
        "proposals_k*": proposals, "phases": phases, "messages": messages,
        "T_ms": round(t_phase + t_eval + t_transfer, 3),
        "phase_ms": round(t_phase, 3), "eval_ms": round(t_eval, 6),
        "transfer_ms": round(t_transfer, 3),
    }
