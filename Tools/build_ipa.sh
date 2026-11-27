#!/bin/bash
# 在 Mac 上生成未签名 IPA。需要 Xcode 命令行工具。
# 用法: Tools/build_ipa.sh [输出目录]
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
build_root="${TDS_CAR_KIT_BUILD_DIR:-/private/tmp/carwithin-ios-build}"
out_dir="${1:-$project_root/build-ipa}"

if [[ ! -f "$project_root/App/BundledIdentity/certificate.p7b" ]]; then
  echo "缺少 App/BundledIdentity 下的 MFi 身份文件（certificate.p7b / leaf.cer / private.x963）。" >&2
  echo "可从官方 CarWithin-1.0.3-unsigned.ipa 的 Payload/TDSCarKit.app/ 中取出。" >&2
  exit 1
fi

TDS_BUNDLE_IDENTIFIER="${TDS_BUNDLE_IDENTIFIER:-com.hanlinzhou.SameDeviceCarPlayPoC}" \
  python3 "$project_root/Tools/generate_project.py"
xcodebuild -project "$project_root/TDSCarKit.xcodeproj" -scheme TDSCarKit \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath "$build_root" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  build

mkdir -p "$out_dir/Payload"
rm -rf "$out_dir/Payload/TDSCarKit.app"
cp -R "$build_root/Build/Products/Release-iphoneos/TDSCarKit.app" "$out_dir/Payload/"
(cd "$out_dir" && rm -f CarWithin-unsigned.ipa && zip -qry CarWithin-unsigned.ipa Payload)
shasum -a 256 "$out_dir/CarWithin-unsigned.ipa"
