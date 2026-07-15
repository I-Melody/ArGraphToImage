# -*- mode: python ; coding: utf-8 -*-
#
# 兼容 Windows 7 / 早期 Win10：api-ms-win-core-path-l1-1-0.dll 是 Python 3.9+
# 依赖的 API Set，旧系统不自带。把该 DLL 从 Win10+ 的 C:\Windows\System32
# 复制到此 spec 同目录下，然后取消下面 binaries=[] → 带 DLL 路径即可。
# 步骤：
#   1. copy C:\Windows\System32\api-ms-win-core-path-l1-1-0.dll .\
#   2. 取消下一行注释
#   3. 重新运行 pyinstaller GraphToImage.spec
# binaries = [('api-ms-win-core-path-l1-1-0.dll', '.')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('word.config', '.'), ('config.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GraphToImage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GraphToImage',
)
