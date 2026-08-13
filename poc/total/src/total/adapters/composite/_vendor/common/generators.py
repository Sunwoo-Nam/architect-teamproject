"""축 값 생성기 — 값은 나열이 아니라 (generator, count)로 정의된다 (c 스윕에서 count만 조절)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Value:
    name: str
    attrs: dict = field(default_factory=dict)


REGIONS = ["gangnam", "hongdae", "yeongdeungpo", "jamsil", "seongsu"]
_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_MENUS = ["korean", "japanese", "chinese", "italian", "mexican", "vegan", "thai", "indian"]
_BUDGETS = ["low", "mid", "high", "premium", "luxury"]
_TRANSPORTS = ["walk", "bus", "subway", "taxi", "car"]


def date_slots(count: int) -> list[Value]:
    out = []
    for i in range(count):
        day = _DAYS[i % 7]
        week = i // 7
        name = day if week == 0 else f"{day}{week + 1}"
        out.append(Value(name, {"weekend": day in ("sat", "sun")}))
    return out


def time_slots(count: int) -> list[Value]:
    out = []
    for i in range(count):
        minutes = 11 * 60 + i * (120 if count <= 6 else 60)
        hh, mm = divmod(minutes, 60)
        out.append(Value(f"{hh:02d}:{mm:02d}", {"late": hh >= 20}))
    return out


def regions(count: int) -> list[Value]:
    names = REGIONS + [f"r{i + 1}" for i in range(len(REGIONS), count)]
    return [Value(n) for n in names[:count]]


def _numbered(prefix: str):
    def gen(count: int) -> list[Value]:
        return [Value(f"{prefix}{i + 1}") for i in range(count)]

    return gen


def _region_linked(prefix: str):
    """지역 소속 값(식당·영화관·카페) — 라운드로빈으로 region 속성을 부여한다."""

    def gen(count: int, region_names: list[str]) -> list[Value]:
        out = []
        for i in range(count):
            region = region_names[i % len(region_names)]
            out.append(Value(f"{prefix}-{region}-{i // len(region_names) + 1}", {"region": region}))
        return out

    return gen


def _fixed(pool: list[str], prefix: str):
    def gen(count: int) -> list[Value]:
        names = pool + [f"{prefix}{i + 1}" for i in range(len(pool), count)]
        return [Value(n) for n in names[:count]]

    return gen


GENERATORS = {
    "date_slots": date_slots,
    "time_slots": time_slots,
    "regions": regions,
    "movies": _numbered("mv"),
    "menus": _fixed(_MENUS, "menu"),
    "budget_bands": _fixed(_BUDGETS, "budget"),
    "transports": _fixed(_TRANSPORTS, "transport"),
}

REGION_LINKED_GENERATORS = {
    "theaters": _region_linked("thtr"),
    "restaurants": _region_linked("rest"),
    "cafes": _region_linked("cafe"),
}


def build_axis_values(generator: str, count: int, region_names: list[str] | None) -> list[Value]:
    if generator in GENERATORS:
        return GENERATORS[generator](count)
    if generator in REGION_LINKED_GENERATORS:
        if not region_names:
            raise ValueError(f"{generator}는 region 축이 먼저 정의되어야 한다")
        return REGION_LINKED_GENERATORS[generator](count, region_names)
    raise ValueError(f"알 수 없는 생성기: {generator}")
