# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for KKA Autonomous 3D Warehouse AGV Simulator.
Bundles Ursina, Panda3D OpenGL/display plugins, all project submodules, and 3D assets
into a standalone zero-clone executable.

Build from repository root:
    pyinstaller --clean packaging/kka_sim.spec
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "assets"), "assets"),
]
binaries = []
hiddenimports = [
    "PIL._tkinter_finder",
    "numpy",
]

for pkg in ("ursina", "panda3d", "direct", "gltf", "simplepbr", "screeninfo"):
    try:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hiddenimports += pkg_hidden
    except Exception:
        pass

hiddenimports += collect_submodules("src")
hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

is_macos = sys.platform == "darwin"
show_console = sys.platform.startswith("linux")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="kka-warehouse-sim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=show_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)

if is_macos:
    app = BUNDLE(
        exe,
        name="KKA-Warehouse-Sim.app",
        bundle_identifier="com.kka.warehouse.sim",
    )
