"""A2A 구조화 메시지의 케이스별 필드 규칙과 coarsening 함수 (02-구조설계 C)."""
import re

FIELD_RULES = {
    "negotiation": {"slot": "time", "area": "location", "budget_cap": "budget",
                    "cuisine": "enum", "party_size": "enum", "note": "freeform"},
    "collaboration": {"can_join": "bool", "role": "enum", "available_window": "time"},
    "knowledge_sharing": {"has_shareable_knowledge": "bool", "summary_level": "enum",
                          "knowledge_category": "enum"},
    "remote_monitoring": {"alert": "bool", "severity": "enum"},
}

DISTRICTS = ["강남", "서초", "송파", "분당", "마포", "용산", "수성", "신촌", "합정", "여의도", "을지로"]


def _first_hour(s):
    m = re.search(r"(\d{1,2}):(\d{2})", str(s))
    return int(m.group(1)) if m else None


def _daypart(h):
    if h is None:
        return None
    if 5 <= h < 11:
        return "아침"
    if 11 <= h < 14:
        return "점심"
    if 14 <= h < 17:
        return "오후"
    if 17 <= h < 23:
        return "저녁"
    return "밤"


def coarsen_time(value, granularity="daypart"):
    if granularity in ("30m", "exact"):
        return str(value)              # 권한보다 느슨 → 정밀도 유지(=결함)
    s = str(value)
    m = re.match(r"\s*([A-Za-z]{3})", s)
    day = (m.group(1) + " ") if m else ""
    dp = _daypart(_first_hour(s))
    return (day + dp).strip() if dp else s


def coarsen_location(value, granularity="district"):
    s = str(value)
    for d in DISTRICTS:
        if d in s:
            return d
    parts = re.split(r"[\s,0-9]", s.strip())
    return parts[0] if parts and parts[0] else s


def coarsen_budget(value, auth):
    return auth.get("budget_disclosure", str(value))


def apply_rule(rtype, value, auth, gran="daypart"):
    if rtype == "time":
        return coarsen_time(value, gran)
    if rtype == "location":
        return coarsen_location(value)
    if rtype == "budget":
        return coarsen_budget(value, auth)
    if rtype == "freeform":
        return None   # 기본: 자유 텍스트 필드는 제거(드롭)
    return value   # enum/bool/int — 그대로
