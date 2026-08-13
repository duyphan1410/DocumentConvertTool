# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = [
    ('assets', 'assets'),
    ('src/i18n/locales', 'src/i18n/locales'),
]
binaries = []
hiddenimports = [
    'src.ui_flet.app',
    'src.ui_flet.state',
    'src.ui_flet.constants',
    'src.ui_flet.native_dialogs',
    'src.ui_flet.theme',
    'src.ui_flet.layout.ribbon_bar',
    'src.ui_flet.layout.footer_bar',
    'src.ui_flet.components.file_path_bar',
    'src.ui_flet.components.search_replace_bar',
    'src.ui_flet.components.formatting_toolbar',
    'src.ui_flet.views.editor_view',
    'src.ui_flet.views.loading_view',
    'src.ui_flet.views.preview_view',
    'src.ui_flet.views.welcome_view',
    'src.ui_flet.views.workspace_view',
    'src.ui_flet.controllers.conversion_controller',
    'src.ui_flet.controllers.editor_controller',
    'src.ui_flet.controllers.file_controller',
    'src.ui_flet.controllers.layout_controller',
    'src.ui_flet.controllers.search_controller',
    'src.ui_flet.controllers.theme_controller',
    'src.ui_flet.helpers.shortcut_manager',
    'src.services.conversion_service',
    'src.services.file_loader',
    'src.services.media_asset_manager',
    'src.core.base_module',
    'src.core.converters',
    'src.core.registry',
    'src.core.validator',
    'src.utils.assets',
    'src.utils.env',
    'src.modules.word_module',
    'src.modules.excel_module',
    'src.modules.pdf_module',
    'src.modules.csv_module',
    'src.modules.html_module',
    'src.modules.pptx_module',
    # Third-party document conversion libraries
    'docx',
    'pptx',
    'openpyxl',
    'mammoth',
    'pdfplumber',
    'fitz',
    'pymupdf',
    'pdfminer',
    'pdfminer.high_level',
    'pdfminer.layout',
    'pypdfium2',
    'markdown_pdf',
    'markdown2',
    'bs4',
    'PIL',
    'cryptography',
]

# Collect binaries & data assets for Flet Desktop framework
tmp_ret = collect_all('flet')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect essential data files for PDF & document processing libraries (fast & lightweight)
for pkg in ['pdfminer', 'pdfplumber', 'pypdfium2', 'fitz']:
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# Collect submodules for PDF engines
for pkg in ['pdfminer', 'fitz']:
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

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
        'pytest',
        'flet.cli',
        'flet.pytest_plugin',
        'flet.testing',
        'unittest',
        'pydoc',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
    optimize=1,
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
    upx_exclude=[
        'pdfium.dll',
        'mupdf.dll',
        'flet.dll',
        'libmpv-2.dll',
        'pdfium',
        'fitz',
        '_fitz',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icons/app_icon.ico'],
)

