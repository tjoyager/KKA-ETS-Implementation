# -*- mode: python ; coding: utf-8 -*-
"""
build_app.spec
==============
PyInstaller specification file untuk membuat Standalone Executable
Simulator Robot Gudang 3D (Autonomous Warehouse AGV - v2.0).

Konfigurasi:
- Mode: onedir (direktori mandiri untuk performa optimal Ursina 3D)
- Target Entry: main.py
- Bundling: Seluruh modul src/, assets/ (models, fonts), models_compressed/,
  serta seluruh aset internal Ursina Engine (models_compressed, textures, fonts, audio, shaders).
"""

import os
import sys
import shutil
from pathlib import Path
import ursina
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT_DIR = Path.cwd().resolve()
URSINA_DIR = Path(ursina.__file__).parent.resolve()

# -----------------------------------------------------------------------------
# 1. KOLEKSI ASET INTERNAL URSINA & PANDA3D
# -----------------------------------------------------------------------------
# Mengumpulkan seluruh aset internal bawaan Ursina Engine
ursina_datas = collect_data_files('ursina')
ursina_submodules = collect_submodules('ursina')

# Mengumpulkan modul dan resource Panda3D
panda3d_datas = collect_data_files('panda3d')
panda3d_submodules = collect_submodules('panda3d')

# -----------------------------------------------------------------------------
# 2. KOLEKSI ASET & KODE SUMBER PROYEK
# -----------------------------------------------------------------------------
project_datas = []

# Aset 3D model, material, dan font kustom
if (ROOT_DIR / 'assets').exists():
    project_datas.append((str(ROOT_DIR / 'assets'), 'assets'))

# Model BAM terkompresi / cache Panda3D jika tersedia
if (ROOT_DIR / 'models_compressed').exists():
    project_datas.append((str(ROOT_DIR / 'models_compressed'), 'models_compressed'))

# Modul kode sumber src/ agar dapat diakses runtime dan dinamis
if (ROOT_DIR / 'src').exists():
    project_datas.append((str(ROOT_DIR / 'src'), 'src'))

# Pastikan primitif mesh bawaan Ursina (cube, quad, sphere, circle)
# juga tersedia di folder models_compressed tingkat root aplikasi
extra_ursina_primitives = []
ursina_models_compressed = URSINA_DIR / 'models_compressed'
if ursina_models_compressed.exists():
    for item in ursina_models_compressed.iterdir():
        if item.is_file():
            extra_ursina_primitives.append((str(item), 'models_compressed'))

# Gabungkan seluruh data files
all_datas = ursina_datas + panda3d_datas + project_datas + extra_ursina_primitives

# -----------------------------------------------------------------------------
# 3. HIDDEN IMPORTS
# -----------------------------------------------------------------------------
all_hiddenimports = sorted(list(set(
    ursina_submodules
    + panda3d_submodules
    + [
        'src',
        'src.config',
        'src.algorithms',
        'src.map_grid',
        'src.simulation',
        'src.cognition',
        'src.cognition.heuristics',
        'src.cognition.pathfinding',
        'src.cognition.warehouse_graph',
        'src.behavior',
        'src.behavior.robot_controller',
        'src.behavior.mission_manager',
        'src.behavior.forklift_controller',
        'src.environment',
        'src.environment.asset_loader',
        'src.environment.warehouse_scene',
        'src.environment.interactive_shelf',
        'src.environment.industrial_facelift',
        'src.environment.warehouse_detailing',
        'src.communication',
        'src.communication.ui_controller',
        'src.communication.hud_serious',
        'src.communication.hud_gamification',
        'src.communication.interaction_system',
        'src.communication.visual_theme',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'numpy',
        'screeninfo',
        'pyperclip',
    ]
)))

block_cipher = None

# Deteksi icon Ursina jika ada
app_icon = None
ursina_ico = URSINA_DIR / 'textures' / 'ursina.ico'
if ursina_ico.exists():
    app_icon = str(ursina_ico)

# -----------------------------------------------------------------------------
# 4. PYINSTALLER ANALYSIS & BUILD GRAPH
# -----------------------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['unittest', 'pytest', 'tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KKA_Warehouse_AGV',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application (bebas dependensi terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='KKA_Warehouse_AGV',
)

# -----------------------------------------------------------------------------
# 5. POST-BUILD: SALIN ASSETS KE ROOT DIST UNTUK AKSES LANGSUNG
# -----------------------------------------------------------------------------
dist_dir = ROOT_DIR / 'dist' / 'KKA_Warehouse_AGV'
if dist_dir.exists():
    src_assets = ROOT_DIR / 'assets'
    dst_assets = dist_dir / 'assets'
    if src_assets.exists():
        if dst_assets.exists():
            shutil.rmtree(dst_assets)
        shutil.copytree(src_assets, dst_assets)

    src_models = ROOT_DIR / 'models_compressed'
    dst_models = dist_dir / 'models_compressed'
    if src_models.exists():
        if dst_models.exists():
            shutil.rmtree(dst_models)
        shutil.copytree(src_models, dst_models)
