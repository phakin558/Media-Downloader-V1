#!/bin/zsh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON=""

for candidate in \
  "$SCRIPT_DIR/python/bin/python3" \
  "$SCRIPT_DIR/python/bin/python3.14" \
  "$SCRIPT_DIR/python/python3"; do
  if [[ -x "$candidate" ]]; then
    PYTHON="$candidate"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "ไม่พบ Portable Python"
  echo "กรุณาดาวน์โหลดและแตกไฟล์ไว้ที่:"
  echo "$SCRIPT_DIR/python/"
  echo "ดูวิธีติดตั้งใน README.md"
  echo "กดปุ่มใดก็ได้เพื่อปิด..."
  read -k 1 REPLY
  exit 1
fi

if ! "$PYTHON" -c "import yt_dlp, pathvalidate" >/dev/null 2>&1; then
  echo "กำลังติดตั้งไลบรารีด้วย Portable Python..."
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$PYTHON" "$SCRIPT_DIR/Media_yt_downloader.py"
