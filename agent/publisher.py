"""발행기 — 승인된 Article을 Astro 콘텐츠 폴더에 마크다운으로 저장한다.
파일 쓰기만 담당. 깃 커밋/푸시는 깃허브 액션이 담당한다(역할 분리).
"""
import re
import unicodedata
from pathlib import Path
from datetime import date

POSTS_DIR = Path(__file__).resolve().parent.parent / "site" / "src" / "content" / "posts"


def _slugify(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).strip().lower()
    value = re.sub(r"[^\w가-힣\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value)
    return value[:60] or "post"


def save(article) -> Path:
    """승인된 Article을 파일로 저장하고 경로를 반환한다."""
    if not article or not article.approved:
        raise ValueError("승인되지 않은 글은 저장할 수 없다.")

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filename = f"{today}-{_slugify(article.title)}.md"
    path = POSTS_DIR / filename

    # 동일 파일명 충돌 방지
    counter = 1
    while path.exists():
        path = POSTS_DIR / f"{today}-{_slugify(article.title)}-{counter}.md"
        counter += 1

    path.write_text(article.full_md, encoding="utf-8")
    print(f"[publisher] 저장 완료: {path.name}")
    return path
