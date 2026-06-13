"""정직성 검증기 — 정보는 살리고, 검증 안 된 단정만 막는다."""
import json, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

LEDGER_PATH = Path(__file__).resolve().parent.parent / "config" / "claim_ledger.json"


@dataclass
class CheckResult:
    passed: bool = True
    blocks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    unclassified_claims: list = field(default_factory=list)


def load_ledger(path: Path = LEDGER_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("claims", {})


def extract_numeric_claims(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?。])\s+|\n", text)
    pattern = re.compile(r"\d+(\.\d+)?\s*(배|%|퍼센트|일|시간|개|종|위)")
    return [s.strip() for s in sentences if pattern.search(s) and s.strip()]


def find_ledger_match(sentence: str, ledger: dict) -> Optional[str]:
    for claim_key in ledger:
        core = [w for w in re.split(r"\s+", claim_key) if len(w) >= 2]
        hits = sum(1 for w in core if w in sentence)
        if core and hits >= max(1, len(core) // 2):
            return claim_key
    return None


ASSERTIVE_ENDINGS = ("이다", "한다", "된다", "입니다", "합니다", "됩니다")
SOURCE_MARKERS = ("따르면", "백서", "자료에", "에 의하면", "주장")


def is_asserted_as_fact(sentence: str) -> bool:
    s = sentence.rstrip(" .!?。")
    has_assertive = any(s.endswith(e) for e in ASSERTIVE_ENDINGS)
    has_source = any(m in sentence for m in SOURCE_MARKERS)
    return has_assertive and not has_source


def check(text: str, ledger: dict | None = None) -> CheckResult:
    if ledger is None:
        ledger = load_ledger()
    result = CheckResult()

    for sentence in extract_numeric_claims(text):
        match = find_ledger_match(sentence, ledger)
        if match is None:
            result.unclassified_claims.append(sentence)
            result.blocks.append(f"미분류 수치 주장 (검증 필요): \"{sentence}\"")
            continue

        entry = ledger[match]
        grade = entry["grade"]

        if grade == "rejected":
            result.blocks.append(f"폐기 등급 주장 포함: \"{sentence}\"")
        elif grade == "sourced_claim":
            if is_asserted_as_fact(sentence):
                result.blocks.append(
                    f"검증 안 된 주장 단정 (출처 명시 필요): \"{sentence}\" → {entry['writing_rule']}")
        elif grade == "verified_fact":
            if entry.get("source") == "PENDING_VERIFICATION" and is_asserted_as_fact(sentence):
                result.blocks.append(
                    f"검증 대기 사실 단정: \"{sentence}\" (1차 출처 확인 전까지 출처 명시 서술)")

    result.passed = not result.blocks
    return result
