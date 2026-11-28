#!/usr/bin/env python3
"""Generate a dependency-free Xcode project for the native iPad/Catalyst app."""
import pathlib, hashlib, json, os, plistlib, subprocess
root = pathlib.Path(__file__).resolve().parents[1]
project = root / 'TDSCarKit.xcodeproj'; project.mkdir(exist_ok=True)
# Keep local signing choices when regenerating an existing project. Explicit environment
# overrides also allow fresh checkouts to be configured without editing generated files.
local_settings = {}
existing = project / 'project.pbxproj'
if existing.exists():
    converted = subprocess.run(['plutil', '-convert', 'xml1', '-o', '-', str(existing)],
                               check=True, capture_output=True)
    previous = plistlib.loads(converted.stdout)['objects']
    for item in previous.values():
        if item.get('isa') == 'PBXNativeTarget' and item.get('name') == 'TDSCarKit':
            configs = previous[item['buildConfigurationList']]['buildConfigurations']
            local_settings = {previous[key]['name']: previous[key]['buildSettings'] for key in configs}
            break
def uid(name): return hashlib.sha1(name.encode()).hexdigest()[:24].upper()
def q(value): return json.dumps(str(value))
objects = []
def add(key, value): objects.append(f'{uid(key)} = {{ {value} }};'); return uid(key)
sources = sorted([*root.glob('App/*.swift'), *root.glob('App/*.m'), *root.glob('App/*.c'), *root.rglob('Sources/TDSCarKitCore/**/*.swift'), *root.glob('Sources/CTDSCarKitCrypto/*.c')])
refs = []; builds = []
for path in sources:
    relative = str(path.relative_to(root))
    filetype = {'.c':'sourcecode.c.c', '.m':'sourcecode.c.objc', '.swift':'sourcecode.swift'}[path.suffix]
    ref = add('ref:'+relative, f'isa = PBXFileReference; lastKnownFileType = {filetype}; path = {q(relative)}; sourceTree = "<group>";')
    refs.append(ref)
    builds.append(add('build:'+relative, f'isa = PBXBuildFile; fileRef = {ref};'))
assets = add('assets', 'isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; path = App/Assets.xcassets; sourceTree = "<group>";')
refs.append(assets)
asset_resource = add('assets-build', f'isa = PBXBuildFile; fileRef = {assets};')
resource_builds = [asset_resource]
# Localized app strings and privacy prompts.
localization_path = 'App/Localization/Localizable.xcstrings'
localization_ref = add('ref:'+localization_path, f'isa = PBXFileReference; lastKnownFileType = text.json.xcstrings; path = {q(localization_path)}; sourceTree = "<group>";')
refs.append(localization_ref)
resource_builds.append(add('build:'+localization_path, f'isa = PBXBuildFile; fileRef = {localization_ref};'))
privacy_children = []
for language in ['en', 'zh-Hans']:
    path = f'App/Localization/{language}.lproj/InfoPlist.strings'
    privacy_children.append(add('ref:'+path, f'isa = PBXFileReference; lastKnownFileType = text.plist.strings; name = {q(language)}; path = {q(path)}; sourceTree = "<group>";'))
privacy_group = add('privacy-localizations', f'isa = PBXVariantGroup; children = ({",".join(privacy_children)},); name = InfoPlist.strings; sourceTree = "<group>";')
refs.append(privacy_group)
resource_builds.append(add('privacy-build', f'isa = PBXBuildFile; fileRef = {privacy_group};'))
for license_path in ['App/KCP-LICENSE.txt', 'App/ANTBMS-LICENSE.txt', 'App/maibms-MIT.txt']:
    license_ref = add('ref:'+license_path, f'isa = PBXFileReference; lastKnownFileType = text; path = {q(license_path)}; sourceTree = "<group>";')
    refs.append(license_ref)
    resource_builds.append(add('build:'+license_path, f'isa = PBXBuildFile; fileRef = {license_ref};'))
receiver_path = 'App/Localization/Receiver.en.html'
receiver_ref = add('ref:'+receiver_path, f'isa = PBXFileReference; lastKnownFileType = text.html; path = {q(receiver_path)}; sourceTree = "<group>";')
refs.append(receiver_ref)
resource_builds.append(add('build:'+receiver_path, f'isa = PBXBuildFile; fileRef = {receiver_ref};'))
# Shared supporter snapshot and offline payment codes.
for path in sorted(root.glob('App/Support/*')):
    relative = str(path.relative_to(root))
    filetype = 'text.json' if path.suffix == '.json' else 'image.png'
    ref = add('ref:'+relative, f'isa = PBXFileReference; lastKnownFileType = {filetype}; path = {q(relative)}; sourceTree = "<group>";')
    refs.append(ref)
    resource_builds.append(add('build:'+relative, f'isa = PBXBuildFile; fileRef = {ref};'))
# CI 兜底：仓库不放身份材料，Actions 上缺它时从本仓库最新 Release 的 IPA 取回，
# 否则产物装好后会停在「尚未导入有效的 MFi 身份」。本地生成工程不受影响。
def fetch_ci_identity():
    import io, urllib.request, zipfile
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    target = root / 'App/BundledIdentity'
    names = ('certificate.p7b', 'leaf.cer', 'private.x963')
    if all((target / name).is_file() for name in names):
        return
    headers = {'Accept': 'application/vnd.github+json'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    repository = os.environ.get('GITHUB_REPOSITORY', '')
    request = urllib.request.Request(f'https://api.github.com/repos/{repository}/releases/latest', headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    urls = [asset['browser_download_url'] for asset in release.get('assets', []) if asset['name'].endswith('.ipa')]
    if not urls:
        raise SystemExit(f'{repository} 最新 Release 中没有 IPA，无法提取 MFi 身份；请在 App/BundledIdentity 放入身份文件后重新构建。')
    with urllib.request.urlopen(urls[0], timeout=300) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        member = next((entry for entry in archive.namelist()
                       if entry.startswith('Payload/') and entry.endswith('/' + name) and entry.count('/') == 2), None)
        if member is None:
            raise SystemExit(f'{urls[0]} 中缺少 {name}')
        (target / name).write_bytes(archive.read(member))
    print(f'已从 {urls[0]} 提取 MFi 身份')


fetch_ci_identity()
# Bundle any staged MFi identity files at the app bundle root so the app can load them directly.
for path in sorted(root.glob('App/BundledIdentity/*')):
    relative = str(path.relative_to(root))
    ref = add('ref:'+relative, f'isa = PBXFileReference; lastKnownFileType = file; path = {q(relative)}; sourceTree = "<group>";')
    refs.append(ref)
    resource_builds.append(add('build:'+relative, f'isa = PBXBuildFile; fileRef = {ref};'))
product = add('product', 'isa = PBXFileReference; explicitFileType = wrapper.application; path = TDSCarKit.app; sourceTree = BUILT_PRODUCTS_DIR;')
products = add('products', f'isa = PBXGroup; name = Products; children = ({product},); sourceTree = "<group>";')
add('group', f'isa = PBXGroup; children = ({",".join(refs + [products])},); sourceTree = "<group>";')
add('sources', f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(builds)},); runOnlyForDeploymentPostprocessing = 0;')
add('resources', f'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(resource_builds)},); runOnlyForDeploymentPostprocessing = 0;')
add('frameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
common = {
'PRODUCT_NAME':'TDSCarKit', 'PRODUCT_BUNDLE_IDENTIFIER':'local.tds.carkit', 'SWIFT_VERSION':'5.0',
'IPHONEOS_DEPLOYMENT_TARGET':'16.0', 'MACOSX_DEPLOYMENT_TARGET':'13.3', 'TARGETED_DEVICE_FAMILY':'1,2',
'SDKROOT':'iphoneos','SUPPORTED_PLATFORMS':'iphoneos iphonesimulator macosx', 'SUPPORTS_MACCATALYST':'YES',
'SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD':'YES', 'DERIVE_MACCATALYST_PRODUCT_BUNDLE_IDENTIFIER':'NO',
'INFOPLIST_FILE':'App/Info.plist', 'GENERATE_INFOPLIST_FILE':'NO', 'ASSETCATALOG_COMPILER_APPICON_NAME':'AppIcon', 'CODE_SIGN_STYLE':'Automatic', 'CODE_SIGN_ENTITLEMENTS':'$(TDS_WIFI_ENTITLEMENTS)', 'TDS_WIFI_NAME_DETECTION':'NO',
'SWIFT_OBJC_BRIDGING_HEADER':'App/TDSCarKit-Bridging-Header.h',
'HEADER_SEARCH_PATHS':'$(SRCROOT)/Sources/CTDSCarKitCrypto/include', 'CLANG_ENABLE_MODULES':'YES',
'CLANG_ENABLE_OBJC_ARC':'YES',
'ENABLE_DEBUG_DYLIB':'NO', 'ENABLE_USER_SCRIPT_SANDBOXING':'YES', 'ENABLE_APP_SANDBOX':'NO',
'LD_RUNPATH_SEARCH_PATHS':'$(inherited) @executable_path/Frameworks',
}
for scope in ['project','target']:
    configs=[]
    for name in ['Debug','Release']:
        settings = dict(common) if scope=='target' else {'CLANG_ENABLE_MODULES':'YES'}
        if scope=='target':
            for key, environment in [('PRODUCT_BUNDLE_IDENTIFIER', 'TDS_BUNDLE_IDENTIFIER'),
                                     ('DEVELOPMENT_TEAM', 'TDS_DEVELOPMENT_TEAM')]:
                value = os.environ.get(environment, local_settings.get(name, {}).get(key, settings.get(key)))
                if value is not None: settings[key] = value
        if scope=='target': settings.update({'SWIFT_OPTIMIZATION_LEVEL':'-O','DEBUG_INFORMATION_FORMAT':'dwarf','SWIFT_ACTIVE_COMPILATION_CONDITIONS':'DEBUG' if name=='Debug' else ''})
        configs.append(add(scope+name, 'isa = XCBuildConfiguration; name = '+name+'; buildSettings = {'+' '.join(f'{k} = {q(v)};' for k,v in settings.items())+'};'))
    add(scope+'configs', f'isa = XCConfigurationList; buildConfigurations = ({",".join(configs)},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
add('target',f'isa = PBXNativeTarget; name = TDSCarKit; productName = TDSCarKit; productReference = {product}; productType = "com.apple.product-type.application"; buildConfigurationList = {uid("targetconfigs")}; buildPhases = ({uid("sources")},{uid("frameworks")},{uid("resources")},); buildRules = (); dependencies = ();')
add('project',f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 1600; }}; buildConfigurationList = {uid("projectconfigs")}; compatibilityVersion = "Xcode 14.0"; developmentRegion = "zh-Hans"; knownRegions = ("zh-Hans", en, Base); mainGroup = {uid("group")}; productRefGroup = {products}; projectDirPath = ""; projectRoot = ""; targets = ({uid("target")},);')
(project/'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n'+'\n'.join(objects)+f'\n}}; rootObject = {uid("project")}; }}\n')
schemes=project/'xcshareddata/xcschemes';schemes.mkdir(parents=True,exist_ok=True)
reference=f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{uid("target")}" BuildableName="TDSCarKit.app" BlueprintName="TDSCarKit" ReferencedContainer="container:TDSCarKit.xcodeproj"/>'
(schemes/'TDSCarKit.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{reference}</BuildActionEntry></BuildActionEntries></BuildAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference}</BuildableProductRunnable></ProfileAction>
<AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>''')
print(project)
