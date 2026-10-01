"""
빌드된 사이트(_site)의 큰 GIF를 MP4로 바꾸고, HTML의 <img>를 <video>로 교체합니다.

- 크기가 MIN_BYTES 미만인 GIF는 그대로 둡니다 (작은 GIF는 변환하면 오히려 커질 수 있음).
- 투명 배경이 있는 GIF는 그대로 둡니다 (MP4는 투명도를 지원하지 않음).
- 변환 결과가 원본보다 크면 그대로 둡니다.
- 한 번 변환한 결과는 .gif-cache에 저장해 다음 빌드에서 재사용합니다.
- 파일 이름에 ".keep."이 들어간 GIF(예: logo.keep.gif)는 변환하지 않습니다.

사용법: python scripts/convert_gifs.py _site
"""
import hashlib
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

MIN_BYTES = 500 * 1024
SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
CACHE = Path(".gif-cache").resolve()


def has_transparency(path: Path) -> bool:
    with Image.open(path) as im:
        frames = getattr(im, "n_frames", 1)
        for i in range(frames):
            im.seek(i)
            if "transparency" in im.info:
                return True
    return False


def convert(gif: Path) -> Path | None:
    digest = hashlib.sha256(gif.read_bytes()).hexdigest()[:20]
    cached = CACHE / f"{digest}.mp4"
    out = gif.with_suffix(".mp4")

    if not cached.exists():
        CACHE.mkdir(exist_ok=True)
        tmp = cached.with_suffix(".tmp.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(gif),
                "-movflags", "+faststart", "-pix_fmt", "yuv420p",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-c:v", "libx264", "-crf", "24", "-preset", "slow", "-an",
                str(tmp),
            ],
            check=True,
        )
        tmp.rename(cached)

    if cached.stat().st_size >= gif.stat().st_size:
        return None
    shutil.copyfile(cached, out)
    return out


def main() -> None:
    converted: dict[str, tuple[int, int]] = {}  # 사이트 기준 경로 -> (가로, 세로)

    for gif in sorted(SITE.rglob("*.gif")):
        rel = gif.relative_to(SITE).as_posix()
        if ".keep." in gif.name or gif.stat().st_size < MIN_BYTES:
            continue
        if has_transparency(gif):
            print(f"건너뜀 (투명 배경): {rel}")
            continue
        out = convert(gif)
        if out is None:
            print(f"건너뜀 (변환 이득 없음): {rel}")
            continue
        with Image.open(gif) as im:
            size = im.size
        converted[rel] = size
        print(f"변환: {rel}  {gif.stat().st_size // 1024}KB → {out.stat().st_size // 1024}KB")

    if not converted:
        print("변환할 GIF가 없습니다.")
        return

    img_tag = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
    attr = re.compile(r'([\w-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')

    def resolve(src: str, page: Path) -> str | None:
        parsed = urlparse(html.unescape(src))
        path = unquote(parsed.path)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return None
        if path.startswith("/"):
            # baseurl이 있어도 맞도록 뒤에서부터 비교
            for key in converted:
                if path == "/" + key or path.endswith("/" + key):
                    return key
            return None
        target = (page.parent / path).resolve()
        try:
            key = target.relative_to(SITE).as_posix()
        except ValueError:
            return None
        return key if key in converted else None

    for page in SITE.rglob("*.html"):
        text = page.read_text(encoding="utf-8")

        def replace(m: re.Match) -> str:
            attrs = {a.group(1).lower(): (a.group(3) if a.group(3) is not None else a.group(4)) for a in attr.finditer(m.group(0))}
            src = attrs.get("src", "")
            key = resolve(src, page)
            if not key:
                return m.group(0)
            w, h = converted[key]
            mp4 = re.sub(r"\.gif(?=($|[?#]))", ".mp4", src, flags=re.IGNORECASE)
            alt = attrs.get("alt", "")
            label = f' aria-label="{alt}"' if alt else ""
            return (
                f'<video class="gif-video" src="{mp4}" width="{attrs.get("width", w)}" '
                f'height="{attrs.get("height", h)}" autoplay loop muted playsinline '
                f'preload="metadata"{label}></video>'
            )

        new = img_tag.sub(replace, text)
        if new != text:
            page.write_text(new, encoding="utf-8")

    # 더 이상 어디서도 쓰지 않는 원본 GIF는 배포본에서 삭제 (용량 절약)
    all_text = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in SITE.rglob("*") if p.suffix in (".html", ".xml", ".json", ".css", ".js"))
    for key in converted:
        name = Path(key).name
        if name not in all_text:
            (SITE / key).unlink()


if __name__ == "__main__":
    main()
