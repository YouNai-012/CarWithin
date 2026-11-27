#!/bin/sh
# 打印 GitHub Actions 需要的三个 Secret 值，直接复制粘贴到仓库
# Settings → Secrets and variables → Actions。
set -eu
dir="$(cd "$(dirname "$0")/../App/BundledIdentity" && pwd)"
for pair in "MFI_P7B_B64:certificate.p7b" "MFI_CER_B64:leaf.cer" "MFI_X963_B64:private.x963"; do
  key="${pair%%:*}"
  file="$dir/${pair##*:}"
  if [ ! -f "$file" ]; then
    echo "缺少 $file" >&2
    exit 1
  fi
  printf '%s=%s\n' "$key" "$(base64 < "$file" | tr -d '\n')"
done
