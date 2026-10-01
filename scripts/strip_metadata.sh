#!/usr/bin/env bash
# 사진에서 위치(GPS), 촬영 기기, 촬영 시각, 작성자 정보 같은 메타데이터를 지웁니다.
# 사진 방향(Orientation)과 색상 프로필(ICC)은 남겨서 사진이 돌아가거나 색이 바뀌지 않게 합니다.
# 지울 정보가 있는 파일만 고치므로, 여러 번 실행해도 같은 파일을 다시 건드리지 않습니다.
#
# 사용법: bash scripts/strip_metadata.sh [폴더나 파일 ...]   (기본값: assets)
set -euo pipefail

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(assets)

if ! command -v exiftool >/dev/null 2>&1; then
  echo "exiftool이 없어 사진 메타데이터를 검사하지 못했어요." >&2
  exit 0
fi

exts=(-ext jpg -ext jpeg -ext png -ext webp -ext heic -ext heif -ext tif -ext tiff)
cond='$GPSLatitude or $GPSPosition or $XMP:GPSLatitude or $SerialNumber or $LensSerialNumber or $OwnerName or $Artist or $Copyright or $DateTimeOriginal or $Make or $Model or $Software or $IPTC:all or $XMP:Creator'

# 1) 지울 정보가 있는 파일 목록
mapfile -t found < <(exiftool -q -q -r "${exts[@]}" -if "$cond" -p '$Directory/$FileName' "${targets[@]}" 2>/dev/null || true)

if [ ${#found[@]} -eq 0 ]; then
  echo "메타데이터를 지울 사진이 없어요."
  exit 0
fi

# 2) 지우기
for f in "${found[@]}"; do
  gps=$(exiftool -q -q -n -p '$GPSLatitude' "$f" 2>/dev/null || true)
  exiftool -q -q -overwrite_original -all= -tagsFromFile @ -Orientation -ICC_Profile "$f"
  if [ -n "$gps" ]; then echo "위치 정보 제거: $f"; else echo "메타데이터 제거: $f"; fi
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "- \`$f\`$([ -n "$gps" ] && echo ' (위치 정보 포함)')" >> "$GITHUB_STEP_SUMMARY"
done
