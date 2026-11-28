#!/bin/bash
# 在 Mac 上生成未签名 IPA。需要 Xcode 命令行工具。
# 用法: [TDS_MFI_SOURCE_IPA=/path/to/CarWithin-*.ipa] Tools/build_ipa.sh [输出目录]
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
build_root="${TDS_CAR_KIT_BUILD_DIR:-/private/tmp/carwithin-ios-build}"
out_dir="${1:-$project_root/build-ipa}"
identity_dir="$project_root/App/BundledIdentity"

identity_names=(certificate.p7b leaf.cer private.x963)
have_identity=true
for name in "${identity_names[@]}"; do
  [[ -f "$identity_dir/$name" ]] || have_identity=false
done

if ! $have_identity; then
  if [[ -n "${TDS_MFI_SOURCE_IPA:-}" ]]; then
    "$project_root/Tools/extract_mfi_identity.sh" "$TDS_MFI_SOURCE_IPA" "$identity_dir"
  else
    echo "缺少 App/BundledIdentity 下的 MFi 身份文件（certificate.p7b / leaf.cer / private.x963）。" >&2
    echo "缺了它也能编译，但安装后 CarPlay 会提示「尚未导入有效的 MFi 身份」。任选其一：" >&2
    echo "  1. 从已有安装包提取：Tools/extract_mfi_identity.sh /path/CarWithin-1.0.6-unsigned.ipa" >&2
    echo "  2. 一步构建：TDS_MFI_SOURCE_IPA=/path/CarWithin-1.0.6-unsigned.ipa Tools/build_ipa.sh" >&2
    echo "  3. 通过 Documents/IdentityImport 导入 Keychain，仅适合 Xcode 调试。" >&2
    exit 1
  fi
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

"$project_root/Tools/extract_mfi_identity.sh" --check "$out_dir/CarWithin-unsigned.ipa"
