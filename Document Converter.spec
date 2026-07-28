# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'src.ui_flet.app',
    'src.ui_flet.native_dialogs',
    'src.ui_flet.preview',
    'src.ui_flet.theme',
    'src.modules.word_module',
    'src.modules.excel_module',
    'src.modules.pdf_module',
    'src.modules.csv_module',
    'src.modules.html_module',
]

# Collect all binaries & data assets for Flet Desktop framework
tmp_ret = collect_all('flet')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas',
        'numpy',
        'matplotlib',
        'scipy',
        'onnxruntime',
        'cryptography',
        'setuptools',
        'distutils',
        'unittest',
        'pytest',
        'wheel',
        'pip',
        'pkg_resources',
        'pdb',
        'flet.cli',
        'flet.pytest_plugin',
        'tkinter.test',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Document Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['favicon.ico'],
)
