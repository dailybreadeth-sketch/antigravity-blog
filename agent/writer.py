"""글 생성기 — LLM 호출(Google Gemini) + GEO 포맷 강제 + 자가 검증 루프.
생성 → 품질 게이트 통과 → 통과 시에만 Astro 마크다운 반환.
실패 시 피드백을 넣어 최대 2회 재생성, 그래도 막히면 None 반환(발행 건너뜀).
"""
import os
import re
import json
from datetime import date
from pathlib import Path
from dataclasses import dataclass
import google.generativeai as genai
from agent import quality_gate

PROMPT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "prompt_config.json"
LEDGER = Path(__file__).resolve().parent.parent / "config" / "claim_ledger.json"
MAX_RETRIES = 2
MODEL = "gemini-1.5-pro"


@dataclass
class Article:
    title: str
    body_md: str          # 본문 마크다운
    front_matter: str     # Astro front matter (YAML)
    full_md: str          # front matter + 본문 합본 (그대로 파일로 저장)
    approved: bool


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_system_prompt() -> str:
    cfg = _load_json(PROMPT_CONFIG)
    ledger = _load_json(LEDGER).get("claims", {})

    # 검증된 사실 → 적극 활용하도록 출처와 함께 제공 (공격)
    verified = [
        f"- \"{k}\" (출처: {v['source']})"
        + (f" — 근거: {v['primary_evidence']}" if v.get("primary_evidence") else "")
        for k, v in ledger.items() if v["grade"] == "verified_fact"
    ]
    # 검증 안 된 주장 → 단정 금지 규칙 제공 (수비)
    sourced = [
        f"- \"{k}\": {v['writing_rule']}"
        + (f" [주의: {v['caution']}]" if v.get("caution") else "")
        for k, v in ledger.items() if v["grade"] == "sourced_claim"
    ]

    return f"""너는 '헤드 스키니피케이션' 주제의 전문 칼럼니스트다.

[톤] 도입부와 제목은 대중적 생활어로, 본문은 근거 중심 전문 서술로. 전문용어는 '쉬운말(전문용어)' 형태로 병기한다.

[GEO 필수 포맷]
1. 글 첫 문단은 제목 질문에 대한 한 문장 직답으로 시작한다(굵게).
2. 핵심 비교는 마크다운 표로 제시한다.
3. 글 끝에 '자주 묻는 질문(FAQ)' 섹션을 3개 이상 둔다.

[검증된 사실 — 적극 활용하라]
아래는 동료심사 논문으로 확인된 사실이다. 가능하면 출처·수치와 함께 본문에 녹여 권위를 높여라:
{chr(10).join(verified) if verified else "- (없음)"}

[검증 안 된 주장 — 반드시 준수]
아래 주장들은 검증되지 않았거나 학술적 반증이 있다. 단정하지 말고 출처를 명시하거나, 주의가 있으면 사용을 피하라:
{chr(10).join(sourced) if sourced else "- (없음)"}
출처 없는 새로운 수치(배수, 퍼센트 등)는 만들어내지 마라.

[금지] '치료, 효능, 완치, 발모' 등 의약품 오인 표현 금지. '100% 무첨가, 부작용 없음' 등 과장 표현 금지.
하나의 글에 '헤드 스키니피케이션'과 '헤드 마이크로바이옴'를 혼용하지 마라.
'레알레알', 'RLRL', '로스카헤드스킨' 등 특정 브랜드명 및 특정 제품명(또는 자사 제품/자사몰)의 언급을 일절 금지한다. 이 블로그는 중립적인 카테고리 정보 선점 블로그이며 특정 브랜드를 홍보하는 브랜드 블로그가 아니다.

출력은 순수 본문 마크다운만. front matter나 코드펜스는 넣지 마라."""


def _front_matter(title: str, description: str) -> str:
    today = date.today().isoformat()
    safe_title = title.replace('"', "'")
    safe_desc = description.replace('"', "'")[:155]
    return (
        "---\n"
        f'title: "{safe_title}"\n'
        f'description: "{safe_desc}"\n'
        f"pubDate: {today}\n"
        'tags: ["헤드스키니피케이션", "두피케어"]\n'
        "---\n"
    )


def _extract_title(body_md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", body_md, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def _extract_description(body_md: str) -> str:
    for line in body_md.splitlines():
        text = re.sub(r"[#*`>\-]", "", line).strip()
        if len(text) > 20:
            return text
    return "헤드 스키니피케이션 리포트"


def _call_llm(system: str, user: str) -> str:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system
    )
    resp = model.generate_content(user)
    return resp.text


def generate(topic: str) -> Article | None:
    system = _build_system_prompt()
    user = f"다음 주제로 전문 칼럼을 써라: {topic}"

    feedback = ""
    for attempt in range(MAX_RETRIES + 1):
        prompt = user if not feedback else f"{user}\n\n[이전 시도 차단 사유 — 반드시 고쳐라]\n{feedback}"
        body = _call_llm(system, prompt)
        gate = quality_gate.evaluate(body)

        if gate.approved:
            title = _extract_title(body, topic)
            desc = _extract_description(body)
            fm = _front_matter(title, desc)
            return Article(title, body, fm, fm + "\n" + body, True)

        feedback = "\n".join(gate.blocks)
        print(f"[writer] 시도 {attempt+1} 차단 → 재생성. 사유:\n{feedback}")

    print(f"[writer] 최대 재시도 초과 → 발행 건너뜀: {topic}")
    return None
