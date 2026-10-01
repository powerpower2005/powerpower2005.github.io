"""
문단 댓글: 빌드된 글 페이지의 문단마다 고유 표시(data-block)를 붙이고,
GitHub Discussions(giscus)에서 문단에 연결된 댓글을 가져와 페이지에 넣습니다.

- 문단 표시는 한국어 원문 내용으로 만듭니다. 영어판은 같은 순서의 문단에 같은 표시를 붙여서
  한국어판과 영어판이 문단 댓글을 함께 씁니다.
- 댓글 첫 줄에 문단 링크(…#b-xxxxxxxx)가 있으면 그 문단의 스레드가 됩니다.
  문단 내용이 바뀌어 표시가 달라지면, 댓글에 인용된 문장과 가장 비슷한 문단에 붙입니다.
- GITHUB_TOKEN이 없으면(내 컴퓨터) 댓글은 가져오지 않고 문단 표시만 붙입니다.
  COMMENTS_FIXTURE=파일.json 으로 테스트용 댓글을 넣을 수 있습니다.

사용법: python scripts/block_comments.py _site
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
BLOCK_SELECTOR = (
    ".post-content > p, .post-content > h2, .post-content > h3, .post-content > h4, "
    ".post-content li, .post-content > blockquote, .post-content > div.highlighter-rouge, "
    ".post-content > table, .post-content > pre"
)
MARKER = re.compile(r"#(b-[0-9a-f]{8}(?:-\d+)?)\b")
DANGEROUS_TAGS = ("script", "style", "iframe", "object", "embed", "form", "input", "button", "link", "meta")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def block_text(el) -> str:
    text = norm(el.get_text(" "))
    if not text:
        text = " ".join(img.get("src", "") for img in el.find_all(["img", "video"]))
    return text


def blocks_of(soup):
    content = soup.select_one(".post-content")
    if not content:
        return []
    return soup.select(BLOCK_SELECTOR)


# ───────────────────────── 문단 표시 붙이기 ─────────────────────────
def assign_ko(soup) -> list[tuple[str, str, str]]:
    """(block_id, 태그, 텍스트) 목록을 돌려주고 data-block을 붙입니다."""
    seen: dict[str, int] = {}
    result = []
    for el in blocks_of(soup):
        text = block_text(el)
        bid = "b-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        seen[bid] = seen.get(bid, 0) + 1
        if seen[bid] > 1:
            bid = f"{bid}-{seen[bid]}"
        el["data-block"] = bid
        result.append((bid, el.name, text))
    return result


def assign_en(soup, ko_blocks) -> list[tuple[str, str, str]]:
    els = blocks_of(soup)
    en_tags = [el.name for el in els]
    ko_tags = [t for _, t, _ in ko_blocks]
    result = []
    matcher = difflib.SequenceMatcher(a=ko_tags, b=en_tags, autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op != "equal":
            continue
        for i, j in zip(range(a0, a1), range(b0, b1)):
            bid = ko_blocks[i][0]
            els[j]["data-block"] = bid
            result.append((bid, els[j].name, block_text(els[j])))
    return result


# ───────────────────────── 댓글 가져오기 ─────────────────────────
QUERY = """
query($owner: String!, $name: String!, $cat: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 50, after: $after, categoryId: $cat) {
      pageInfo { hasNextPage endCursor }
      nodes {
        title
        url
        comments(first: 100) {
          nodes {
            url createdAt bodyHTML isMinimized
            author { login avatarUrl url }
            replies(first: 50) {
              nodes { url createdAt bodyHTML isMinimized author { login avatarUrl url } }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_discussions() -> dict[str, list]:
    fixture = os.environ.get("COMMENTS_FIXTURE")
    if fixture:
        return json.loads(Path(fixture).read_text(encoding="utf-8"))

    token = os.environ.get("GITHUB_TOKEN")
    cfg = yaml.safe_load(Path("_config.yml").read_text(encoding="utf-8"))
    g = cfg.get("giscus") or {}
    if not token or not g.get("repo") or not g.get("category_id"):
        print("댓글을 가져오지 않았어요 (GITHUB_TOKEN 또는 giscus 설정 없음). 문단 표시만 붙입니다.")
        return {}

    owner, name = g["repo"].split("/", 1)
    out: dict[str, list] = {}
    after = None
    while True:
        payload = json.dumps({"query": QUERY, "variables": {"owner": owner, "name": name, "cat": g["category_id"], "after": after}})
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload.encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        if data.get("errors"):
            print(f"::warning::댓글을 가져오지 못했어요: {data['errors'][0].get('message')}")
            return out
        d = data["data"]["repository"]["discussions"]
        for node in d["nodes"]:
            out[node["title"]] = node["comments"]["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        after = d["pageInfo"]["endCursor"]


# ───────────────────────── 댓글 정리 ─────────────────────────
def clean_html(html: str) -> tuple[str, str]:
    """댓글 HTML에서 위험한 요소와 문단 표시 줄을 지우고 (본문, 인용문)을 돌려줍니다."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(DANGEROUS_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on") or (attr in ("href", "src") and str(tag[attr]).strip().lower().startswith("javascript:")):
                del tag[attr]
        if tag.name == "a":
            tag["target"] = "_blank"
            tag["rel"] = "noopener nofollow ugc"

    quote = ""
    first = soup.find(["p", "a"])
    if first and MARKER.search(str(first)):
        nxt = first.find_next_sibling()
        first.decompose()
        if nxt is not None and nxt.name == "blockquote":
            quote = norm(nxt.get_text(" "))
            nxt.decompose()
    return str(soup).strip(), quote


OWNER = ""


def simplify(c: dict) -> dict:
    body, _ = clean_html(c.get("bodyHTML", ""))
    a = c.get("author") or {}
    return {
        "owner": bool(OWNER) and a.get("login", "").lower() == OWNER.lower(),
        "author": a.get("login", "ghost"),
        "avatar": a.get("avatarUrl", ""),
        "profile": a.get("url", ""),
        "url": c.get("url", ""),
        "date": (c.get("createdAt") or "")[:10],
        "html": body,
    }


def threads_for(comments: list, ko_blocks, en_blocks) -> dict[str, list]:
    ids = {b for b, _, _ in ko_blocks}
    texts = [(b, t) for b, _, t in ko_blocks] + [(b, t) for b, _, t in en_blocks]
    threads: dict[str, list] = {}
    for c in comments:
        if c.get("isMinimized"):
            continue
        html = c.get("bodyHTML", "")
        m = MARKER.search(html)
        if not m:
            continue
        bid = m.group(1)
        if bid not in ids:
            _, quote = clean_html(html)
            best, score = None, 0.0
            for b, t in texts:
                s = difflib.SequenceMatcher(a=quote, b=t[: len(quote) + 20]).ratio() if quote else 0
                if s > score:
                    best, score = b, s
            if not best or score < 0.6:
                continue
            bid = best
        item = simplify(c)
        item["replies"] = [simplify(r) for r in (c.get("replies") or {}).get("nodes", []) if not r.get("isMinimized")]
        threads.setdefault(bid, []).append(item)
    return threads


# ───────────────────────── 실행 ─────────────────────────
def load(path: Path):
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def main():
    global OWNER
    try:
        cfg = yaml.safe_load(Path("_config.yml").read_text(encoding="utf-8")) or {}
        OWNER = os.environ.get("BLOG_OWNER") or str((cfg.get("giscus") or {}).get("repo", "")).split("/")[0]
    except OSError:
        pass
    ko_pages, en_pages = {}, []
    for page in SITE.rglob("index.html"):
        soup = load(page)
        if not soup.select_one(".post-content"):
            continue
        lang = (soup.html.get("lang") if soup.html else "") or ""
        if lang.startswith("en"):
            en_pages.append((page, soup))
        else:
            canonical = soup.find("link", rel="canonical")
            ko_pages[canonical["href"] if canonical else str(page)] = (page, soup)

    ko_info = {}
    for key, (page, soup) in ko_pages.items():
        ko_info[key] = assign_ko(soup)

    en_info = {}
    for page, soup in en_pages:
        alt = soup.find("link", rel="alternate", hreflang="ko")
        ko_key = alt["href"] if alt else None
        if ko_key in ko_info:
            en_info[ko_key] = (page, soup, assign_en(soup, ko_info[ko_key]))

    discussions = fetch_discussions()
    total = 0

    def write(page: Path, soup, threads: dict):
        if threads:
            tag = soup.new_tag("script", type="application/json", id="block-threads")
            tag.string = json.dumps({"threads": threads}, ensure_ascii=False).replace("</", "<\\/")
            soup.body.append(tag)
        page.write_text(str(soup), encoding="utf-8")

    for key, (page, soup) in ko_pages.items():
        box = soup.find(id="giscus")
        term = box.get("data-term") if box else None
        en = en_info.get(key)
        threads = threads_for(discussions.get(term, []), ko_info[key], en[2] if en else []) if term else {}
        total += sum(len(v) for v in threads.values())
        write(page, soup, threads)
        if en:
            write(en[0], en[1], threads)

    for page, soup in en_pages:
        if not any(page == e[0] for e in en_info.values()):
            page.write_text(str(soup), encoding="utf-8")

    print(f"문단 표시: 글 {len(ko_pages)}편 (영어판 {len(en_info)}편 연결), 문단 댓글 {total}개")


if __name__ == "__main__":
    main()
