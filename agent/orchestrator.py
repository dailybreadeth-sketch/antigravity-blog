"""오케스트레이터 — 전체 발행 파이프라인 지휘.
주제 선택 → 글 생성(+자가검증) → 저장 → 클러스터 기억 갱신.
승인 글이 없으면 발행을 건너뛴다(무조건 발행 안 함).
"""
import sys
import json
from pathlib import Path
from agent import trend_tracker, writer, publisher, quality_gate

MEMORY = Path(__file__).resolve().parent.parent / "data" / "blog_memory.json"


def _load_memory() -> dict:
    with open(MEMORY, encoding="utf-8") as f:
        return json.load(f)


def _save_memory(memory: dict):
    with open(MEMORY, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def _mark_covered(memory: dict, topic: str):
    if topic not in memory["covered_angles"]:
        memory["covered_angles"].append(topic)
    if memory["cluster_map"]["hub"]["title"] == topic:
        memory["cluster_map"]["hub"]["status"] = "published"


def run_pipeline() -> bool:
    memory = _load_memory()

    candidate = trend_tracker.select_next_topic(memory)
    print(f"[orchestrator] 선택된 주제: {candidate.topic} "
          f"(source={candidate.source}, priority={candidate.priority})")

    if candidate.topic == "REFRESH_EXISTING":
        print("[orchestrator] 신규 각도 소진 — 이번 슬롯은 기존 글 갱신 대상. 발행 건너뜀.")
        return False

    article = writer.generate(candidate.topic)
    if article is None:
        print("[orchestrator] 품질 게이트 통과 글 생성 실패 — 발행 건너뜀.")
        return False

    path = publisher.save(article)
    _mark_covered(memory, candidate.topic)
    _save_memory(memory)
    print(f"[orchestrator] ✅ 발행 완료: {path.name}")
    return True


def self_test():
    """API 키 없이 검증 로직만 점검 (기존 자가 테스트 유지)."""
    samples = {
        "검증 안 된 단정 (차단 기대)": "두피는 얼굴보다 6배 빠르게 노화한다.",
        "출처 명시 (통과 기대)": "브랜드 백서에 따르면 두피는 얼굴보다 6배 빠르게 노화한다고 한다.",
        "명칭 혼용 (차단 기대)": "헤드 스키니피케이션과 헤드 마이크로바이옴를 함께 적용한다.",
    }
    for label, text in samples.items():
        gate = quality_gate.evaluate(text)
        print(f"[{label}] → {'승인' if gate.approved else '차단'}")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        run_pipeline()
