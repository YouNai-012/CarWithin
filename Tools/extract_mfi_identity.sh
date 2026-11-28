#!/bin/bash
# 从已有的未签名 IPA 中取出 MFi 配件身份三件套，或校验某个 IPA 是否内置身份。
# 用法:
#   Tools/extract_mfi_identity.sh <CarWithin-*.ipa> [输出目录]   默认写入 App/BundledIdentity
#   Tools/extract_mfi_identity.sh --check <CarWithin-*.ipa>      只校验，不写文件
set -euo pipefail

check_only=false
if [[ "${1:-}" == "--check" ]]; then
  check_only=true
  shift
fi
ipa="${1:-}"
usage() { echo "用法: $0 [--check] <CarWithin-*.ipa> [输出目录]" >&2; exit 2; }
[[ -n "$ipa" && -f "$ipa" ]] || usage
command -v unzip >/dev/null || { echo "需要 unzip" >&2; exit 1; }

root="$(cd "$(dirname "$0")/.." && pwd)"
files="$(unzip -Z1 "$ipa")"
app_prefix="$(printf '%s\n' "$files" | sed -n 's|^\(Payload/[^/]*\.app\)/.*|\1|p' | sort -u | head -n 1)"
[[ -n "$app_prefix" ]] || { echo "$ipa 中没有 Payload/*.app" >&2; exit 1; }

names=(certificate.p7b leaf.cer private.x963)
missing=()
for name in "${names[@]}"; do
  printf '%s\n' "$files" | grep -Fxq "$app_prefix/$name" || missing+=("$name")
done
if ((${#missing[@]})); then
  echo "$ipa 不含 MFi 身份文件（缺 ${missing[*]}）" >&2
  exit 1
fi
if $check_only; then
  echo "$ipa 已内置 MFi 身份：${names[*]}"
  exit 0
fi

out="${2:-$root/App/BundledIdentity}"
mkdir -p "$out"
for name in "${names[@]}"; do
  unzip -p "$ipa" "$app_prefix/$name" > "$out/$name"
done

# private.x963 是 X9.63 未压缩 P-256 私钥：97 字节、首字节 0x04。不符说明取到了错误文件。
size="$(wc -c < "$out/private.x963" | tr -d ' ')"
[[ "$size" == 97 ]] || { echo "private.x963 应为 97 字节，实际 $size" >&2; exit 1; }
[[ "$(od -An -tu1 -N1 "$out/private.x963" | tr -d ' \n')" == 4 ]] || {
  echo "private.x963 不是未压缩点格式（首字节应为 0x04）" >&2
  exit 1
}

echo "已写入 $out"
for name in "${names[@]}"; do
  printf '  %-16s %6s 字节\n' "$name" "$(wc -c < "$out/$name" | tr -d ' ')"
done
