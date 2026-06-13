"""품질 게이트 — 정직성 검증 + 마케팅 가이드라인 종합 평가."""
import json
from pathlib import Path
from dataclasses import dataclass, field
from agent import honesty_checker

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "quality_gate.json"


@dataclass
class GateResult:
    approved: bool = True
    blocks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _scan_terms(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in text]


def evaluate(text: str, config: dict | None = None) -> GateResult:
    if config is None:
        config = load_config()
    checks = config.get("checks", {})
    result = GateResult()

    if checks.get("honesty", {}).get("enabled"):
        h = honesty_checker.check(text)
        result.blocks += h.blocks
        result.warnings += h.warnings

    for name in ("medical_terms", "exaggeration"):
        c = checks.get(name, {})
        if c.get("enabled"):
            found = _scan_terms(text, c.get("terms", []))
            for term in found:
                msg = f"[{name}] 주의 표현 발견: '{term}'"
                (result.blocks if c.get("on_fail") == "block" else result.warnings).append(msg)

    cm = checks.get("channel_mixing", {})
    if cm.get("enabled"):
        present = _scan_terms(text, cm.get("exclusive_terms", []))
        if len(present) > 1:
            result.blocks.append(
                f"[channel_mixing] 배타 명칭 혼용 금지: {present}")

    result.approved = not result.blocks
    return result
