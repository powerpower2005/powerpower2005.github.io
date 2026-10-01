#!/usr/bin/env bash
# 내 컴퓨터에서 커밋하기 전에 사진 메타데이터를 자동으로 지우는 훅을 설치합니다.
# 저장소 폴더에서 한 번만 실행: bash scripts/install-hooks.sh
set -euo pipefail
hook=".git/hooks/pre-commit"
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
mapfile -t files < <(git diff --cached --name-only --diff-filter=ACM | grep -iE '\.(jpe?g|png|webp|heic|heif|tiff?)$' || true)
[ ${#files[@]} -eq 0 ] && exit 0
if ! command -v exiftool >/dev/null 2>&1; then
  echo "알림: exiftool을 설치하면 커밋 전에 사진 위치 정보를 지울 수 있어요. (macOS: brew install exiftool)"
  exit 0
fi
bash scripts/strip_metadata.sh "${files[@]}"
git add -- "${files[@]}"
HOOK
chmod +x "$hook"
echo "설치했어요. 이제 커밋할 때 사진 메타데이터가 자동으로 지워집니다."
