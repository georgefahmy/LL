# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "assets"), "assets"),
]

seed_gz = ROOT / "seed_questions.json.gz"
if seed_gz.is_file():
    datas.append((str(seed_gz), "."))

datas += collect_data_files("statsmodels")

hiddenimports = (
    [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "pydantic_settings",
        "lxml.etree",
        "lxml._elementpath",
        "rapidfuzz",
        "cryptography",
        "httpx",
        "bs4",
        "backend.core.browser_worker",
        "backend.core.browser_session",
        "backend.core.ocr",
        "backend.api.routes.extension",
    ]
    + collect_submodules("keyring.backends")
    + collect_submodules("webview")
)

icon_path = str(
    ROOT / "assets" / ("ll_logo.icns" if sys.platform == "darwin" else "ll_logo.ico")
)

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LearnedLeague",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LearnedLeague",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="LearnedLeague.app",
        icon=icon_path,
        bundle_identifier="com.georgefahmy.learnedleague",
        info_plist={
            "CFBundleShortVersionString": "9.0.0",
            "CFBundleVersion": "9.0.0",
            "NSHighResolutionCapable": True,
        },
    )
