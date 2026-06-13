"""트렌드 수집기 — '무엇을 쓸지' 결정.
클러스터의 빈 각도(우선) + 외부 트렌드 신호(가중)를 섞어 다음 주제를 고른다.
1단계: 키 불필요한 소스. 2단계에서 공식 API로 교체 가능하도록 인터페이스 추상화.
"""
import json
import random
from pathlib import Path
from dataclasses import dataclass

MEMORY = Path(__file__).resolve().parent.parent / "data" / "blog_memory.json"
SEED_KEYWORDS = ["두피 노화", "정수리 냄새", "두피 케어", "스칼프케어", "두피 건조"]


@dataclass
class TopicCandidate:
    topic: str
    source: str       # "empty_cluster" | "trend"
    priority: float


def _load_memory() -> dict:
    with open(MEMORY, encoding="utf-8") as f:
        return json.load(f)


def get_empty_angles(memory: dict) -> list[str]:
    covered = set(memory.get("covered_angles", []))
    all_spokes = [t for group in memory["cluster_map"]["spokes"].values() for t in group]
    if memory["cluster_map"]["hub"]["status"] == "empty":
        all_spokes = [memory["cluster_map"]["hub"]["title"]] + all_spokes
    return [t for t in all_spokes if t not in covered]


def fetch_trend_signals(keywords: list[str] = None) -> list[str]:
    """외부 트렌드 급상승어 수집. 1단계: pytrends 시도, 실패 시 빈 리스트로 안전 폴백."""
    keywords = keywords or SEED_KEYWORDS
    try:
        import socket
        socket.setdefaulttimeout(3)  # 무한 대기 방지
        from pytrends.request import TrendReq
        py = TrendReq(hl="ko-KR", tz=540, timeout=3)
        py.build_payload(keywords[:5], timeframe="now 7-d", geo="KR")
        related = py.related_queries()
        rising = []
        for kw, data in related.items():
            if data and data.get("rising") is not None:
                rising += data["rising"]["query"].tolist()[:3]
        return rising
    except Exception as e:
        print(f"[trend] 외부 트렌드 수집 실패, 폴백 진행: {e}")
        return []


def select_next_topic(memory: dict = None) -> TopicCandidate:
    if memory is None:
        memory = _load_memory()

    empty = get_empty_angles(memory)
    trends = fetch_trend_signals()

    # 허브가 비어있으면 무조건 허브 먼저 (권위의 중심)
    hub = memory["cluster_map"]["hub"]
    if hub["status"] == "empty" and hub["title"] in empty:
        return TopicCandidate(hub["title"], "empty_cluster", 1.0)

    # 빈 각도 중 트렌드 키워드와 겹치는 게 있으면 우선순위 가산
    if empty:
        scored = []
        for angle in empty:
            boost = sum(0.3 for t in trends if any(w in angle for w in t.split()))
            scored.append(TopicCandidate(angle, "empty_cluster", 0.6 + boost))
        scored.sort(key=lambda c: c.priority, reverse=True)
        return scored[0]

    # 모든 각도가 채워졌으면 트렌드 기반 신규 주제
    if trends:
        return TopicCandidate(random.choice(trends), "trend", 0.5)

    # 최후 폴백: 기존 글 갱신 신호 (휘발성 양산 방지)
    return TopicCandidate("REFRESH_EXISTING", "trend", 0.1)
