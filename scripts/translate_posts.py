"""
한국어 글(_posts)을 영어로 기계 번역해 _en_posts 에 저장합니다.

- 새 글이나 내용이 바뀐 글만 번역합니다 (source_hash로 비교).
- 번역본 front matter에 translation_locked: true 가 있으면 덮어쓰지 않습니다.
- 원본 글에 translate: false 가 있으면 번역하지 않습니다.
- 원본이 지워진 번역본은 함께 지웁니다 (잠긴 번역본은 남기고 경고).
- 코드 블록, 인라인 코드, 링크 주소, 이미지 주소, HTML, Liquid 태그는 번역하지 않습니다.
- _data/glossary.yml 의 용어는 항상 같은 영어로 바꿉니다.

사용법:
  python scripts/translate_posts.py --check   # 번역할 글이 있는지만 확인 (needed=true/false 출력)
  python scripts/translate_posts.py           # 번역 실행

번역 엔진은 TRANSLATOR 환경 변수로 고릅니다.
  opus (기본값)  Actions 안에서 OPUS-MT 모델을 직접 실행
  mock           테스트용 (실제 번역 없이 표시만 붙임)
다른 엔진(API 등)을 쓰려면 Translator 클래스를 하나 더 만들면 됩니다.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sys
from pathlib import Path

import yaml

SRC = Path("_posts")
DST = Path("_en_posts")
GLOSSARY = Path("_data/glossary.yml")
MODEL = os.environ.get("TRANSLATION_MODEL", "Helsinki-NLP/opus-mt-tc-big-ko-en")
VERSION = "1"  # 번역 규칙을 바꿨을 때 올리면 전체를 다시 번역합니다

HANGUL = re.compile(r"[\uac00-\ud7a3\u3131-\u318e]")
DATE_PREFIX = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}-")
PH = re.compile(r"\[(1\d\d)\]")  # 자리표시자: [100], [101], ...


# ───────────────────────── 번역 엔진 ─────────────────────────
class Translator:
    def translate(self, texts: list[str]) -> list[str]:
        raise NotImplementedError


class MockTranslator(Translator):
    """테스트용: 문장을 «...»로 감쌉니다. MOCK_DROP=1이면 자리표시자를 일부러 망가뜨립니다."""

    def translate(self, texts):
        out = []
        for t in texts:
            if os.environ.get("MOCK_DROP") and PH.search(t):
                t = PH.sub("", t, count=1)
            out.append(f"«{t}»")
        return out


class OpusTranslator(Translator):
    def __init__(self, name: str = MODEL):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch.set_num_threads(os.cpu_count() or 2)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(name).eval()

    def translate(self, texts):
        results = []
        for i in range(0, len(texts), 8):
            batch = texts[i : i + 8]
            enc = self.tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
            with self.torch.no_grad():
                out = self.model.generate(**enc, num_beams=4, max_new_tokens=512)
            results.extend(self.tok.batch_decode(out, skip_special_tokens=True))
        return results


class CachedTranslator:
    """같은 문장은 한 번만 번역합니다."""

    def __init__(self, engine: Translator):
        self.engine = engine
        self.cache: dict[str, str] = {}

    def __call__(self, texts: list[str]) -> list[str]:
        todo = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if todo:
            for src, dst in zip(todo, self.engine.translate(todo)):
                self.cache[src] = dst.strip()
        return [self.cache[t] for t in texts]


# ───────────────────────── 문장 단위 번역 ─────────────────────────
INLINE = re.compile(
    r"(?P<code>`+[^`]+?`+)"
    r"|(?P<image>!\[(?P<alt>[^\]]*)\]\((?P<isrc>[^)\s]+(?:\s+\"[^\"]*\")?)\))"
    r"|(?P<link>\[(?P<ltext>[^\]]+)\]\((?P<href>[^)\s]+(?:\s+\"[^\"]*\")?)\))"
    r"|(?P<autolink><https?://[^>]+>)"
    r"|(?P<url>https?://[^\s)]+)"
    r"|(?P<liquid>\{\{.*?\}\}|\{%.*?%\})"
    r"|(?P<html><[^>]+>)"
    r"|(?P<strong>\*\*(?P<stext>[^*]+)\*\*|__(?P<stext2>[^_]+)__)"
    r"|(?P<em>(?<![*\w])\*(?P<etext>[^*\s][^*]*?)\*(?!\*))"
    r"|(?P<existing>\[1\d\d\])"
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class Engine:
    def __init__(self, translate: CachedTranslator, glossary: dict[str, str]):
        self.tr = translate
        self.glossary = sorted(glossary.items(), key=lambda kv: -len(kv[0]))

    def inline(self, text: str) -> str:
        """한 줄(또는 한 문단)을 번역합니다. 마크다운 문법은 보존합니다."""
        if not HANGUL.search(text):
            return text
        values: list[str] = []

        def hold(value: str) -> str:
            values.append(value)
            return f"[{100 + len(values) - 1}]"

        def protect(m: re.Match) -> str:
            if m.group("image") is not None:
                return hold(f"![{self.inline(m.group('alt'))}]({m.group('isrc')})")
            if m.group("link") is not None:
                return hold(f"[{self.inline(m.group('ltext'))}]({m.group('href')})")
            if m.group("strong") is not None:
                inner = m.group("stext") or m.group("stext2")
                return hold(f"**{self.inline(inner)}**")
            if m.group("em") is not None:
                return hold(f"*{self.inline(m.group('etext'))}*")
            return hold(m.group(0))

        protected = INLINE.sub(protect, text)
        for ko, en in self.glossary:
            if ko in protected:
                protected = protected.replace(ko, hold(en))

        sentences = SENTENCE_END.split(protected)
        translated = [self._sentence(s) for s in sentences]
        result = " ".join(translated)
        return PH.sub(lambda m: values[int(m.group(1)) - 100], result)

    def _sentence(self, s: str) -> str:
        if not HANGUL.search(s):
            return s
        wanted = PH.findall(s)
        out = self.tr([s])[0]
        if sorted(PH.findall(out)) == sorted(wanted):
            return out
        # 번역기가 자리표시자를 망가뜨리면, 자리표시자 사이 조각을 따로 번역해 이어 붙입니다.
        parts = re.split(r"(\[1\d\d\])", s)
        pieces = [p for p in parts if p and not PH.fullmatch(p) and HANGUL.search(p)]
        done = iter(self.tr([p.strip() for p in pieces]))
        rebuilt = []
        for p in parts:
            if p and not PH.fullmatch(p) and HANGUL.search(p):
                lead = " " if p[:1].isspace() else ""
                trail = " " if p[-1:].isspace() else ""
                rebuilt.append(lead + next(done) + trail)
            else:
                rebuilt.append(p)
        return "".join(rebuilt)


# ───────────────────────── 마크다운 문서 처리 ─────────────────────────
FENCE = re.compile(r"^\s*(```+|~~~+)")
HEADING = re.compile(r"^(#{1,6}\s+)(.*?)(\s*\{#[^}]+\})?$")
PREFIX = re.compile(r"^((?:\s*>)*\s*(?:(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?)?)(.*)$")


def translate_body(body: str, eng: Engine) -> str:
    out: list[str] = []
    para: list[str] = []
    fence: str | None = None

    def flush():
        if para:
            out.append(eng.inline(" ".join(l.strip() for l in para)))
            para.clear()

    for line in body.split("\n"):
        if fence:
            out.append(line)
            if line.strip().startswith(fence):
                fence = None
            continue
        m = FENCE.match(line)
        if m:
            flush()
            fence = m.group(1)[:3]
            out.append(line)
            continue
        stripped = line.strip()
        if not stripped or not HANGUL.search(line) or stripped.startswith(("<", "{%", "{{")):
            flush()
            out.append(line)
            continue
        h = HEADING.match(line)
        if h:
            flush()
            out.append(h.group(1) + eng.inline(h.group(2)) + (h.group(3) or ""))
            continue
        if stripped.startswith("|"):
            flush()
            cells = line.split("|")
            out.append("|".join((" " + eng.inline(c.strip()) + " ") if HANGUL.search(c) else c for c in cells))
            continue
        p = PREFIX.match(line)
        if p and p.group(1):
            flush()
            out.append(p.group(1) + eng.inline(p.group(2)))
            continue
        para.append(line)
    flush()
    return "\n".join(out)


# ───────────────────────── 파일 처리 ─────────────────────────
def split_front_matter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = yaml.safe_load(text[3:end]) or {}
            body = text[end + 4 :].lstrip("\n")
            return fm, body
    return {}, text


def to_text(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def pretty_slug(s: str) -> str:
    s = re.sub(r"[^\w.~!$&'()+,;=@-]+", "-", s, flags=re.UNICODE)
    return re.sub(r"-{2,}", "-", s).strip("-")


def source_hash(fm: dict, body: str) -> str:
    keep = {k: to_text(fm.get(k)) for k in ("title", "description", "date", "image")}
    raw = VERSION + yaml.safe_dump(keep, allow_unicode=True, sort_keys=True) + body
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def plan():
    """(원본, 번역본 경로, 원본 front matter, 본문, 해시) 목록과 지울 번역본 목록을 돌려줍니다."""
    todo, stale_locked = [], []
    sources = {}
    for src in sorted(SRC.glob("*.md")) + sorted(SRC.glob("*.markdown")):
        fm, body = split_front_matter(src.read_text(encoding="utf-8"))
        if fm.get("translate") is False or fm.get("published") is False:
            continue
        sources[src.stem] = src
        dst = DST / (src.stem + ".md")
        h = source_hash(fm, body)
        if dst.exists():
            old, _ = split_front_matter(dst.read_text(encoding="utf-8"))
            if old.get("translation_locked"):
                if old.get("source_hash") != h:
                    stale_locked.append(dst)
                continue
            if old.get("source_hash") == h:
                continue
        todo.append((src, dst, fm, body, h))

    orphans = []
    if DST.exists():
        for dst in DST.glob("*.md"):
            if dst.stem not in sources:
                old, _ = split_front_matter(dst.read_text(encoding="utf-8"))
                orphans.append((dst, bool(old.get("translation_locked"))))
    return todo, stale_locked, orphans


def summary(line: str):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main():
    todo, stale_locked, orphans = plan()

    for dst in stale_locked:
        print(f"::warning::원문이 바뀌었지만 잠긴 번역이라 그대로 두었어요: {dst}", file=sys.stderr)

    if "--check" in sys.argv:
        needed = bool(todo) or any(not locked for _, locked in orphans)
        print(f"needed={'true' if needed else 'false'}")
        for src, *_ in todo:
            print(f"번역 예정: {src}", file=sys.stderr)
        return

    for dst, locked in orphans:
        if locked:
            print(f"::warning::원본 글이 없지만 잠긴 번역이라 남겨두었어요: {dst}")
        else:
            dst.unlink()
            print(f"삭제: {dst} (원본 글이 없음)")

    if not todo:
        print("번역할 글이 없어요.")
        return

    glossary = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8")) if GLOSSARY.exists() else {}
    name = os.environ.get("TRANSLATOR", "opus")
    engine_impl = MockTranslator() if name == "mock" else OpusTranslator()
    eng = Engine(CachedTranslator(engine_impl), {str(k): str(v) for k, v in (glossary or {}).items()})

    DST.mkdir(exist_ok=True)
    summary("### 영어로 번역한 글")
    for src, dst, fm, body, h in todo:
        slug = fm.get("slug") or DATE_PREFIX.sub("", src.stem)
        if fm.get("permalink"):
            permalink = "/en" + "/" + str(fm["permalink"]).lstrip("/")
        else:
            permalink = f"/en/blog/{pretty_slug(str(slug))}/"

        new_fm = {
            "title": eng.inline(str(fm.get("title", ""))),
            "date": to_text(fm.get("date")) if fm.get("date") else None,
            "description": eng.inline(str(fm["description"])) if fm.get("description") else None,
            "image": fm.get("image"),
            "permalink": permalink,
            "ref": src.stem,
            "project": fm.get("project"),
            "comments": fm.get("comments"),
            "toc": fm.get("toc"),
            "machine_translated": True,
            "translation_locked": False,
            "source_hash": h,
        }
        new_fm = {k: v for k, v in new_fm.items() if v is not None}
        header = (
            "# 이 파일은 scripts/translate_posts.py가 자동으로 만들었습니다.\n"
            "# 직접 고친 뒤 translation_locked: true 로 바꾸면 다시 번역하지 않습니다.\n"
            "# 사람이 검토했다면 machine_translated: false 로 바꾸세요 (안내 문구가 바뀝니다).\n"
        )
        text = "---\n" + header + yaml.safe_dump(new_fm, allow_unicode=True, sort_keys=False) + "---\n\n"
        text += translate_body(body, eng).rstrip() + "\n"
        dst.write_text(text, encoding="utf-8")
        print(f"번역: {src} → {dst}")
        summary(f"- `{src.name}` → [{new_fm['title']}]({permalink})")


if __name__ == "__main__":
    main()
