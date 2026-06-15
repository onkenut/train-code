import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
APP_NAME = "PixelVault"
ENTRY_POINT = "pixelvault.app:main"
ICON_PATH = ROOT_DIR / "assets" / "icon.ico"

ONNX_MODELS_DIR = ROOT_DIR / "models"


def check_dependencies():
    try:
        import PySide6
        import PIL
        import cv2
        import numpy
        import sklearn
        print("All core dependencies available.")
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Please run: poetry install")
        return False


def build_spec():
    datas = []
    hiddenimports = [
        "pixelvault", "pixelvault.database", "pixelvault.core", "pixelvault.ai",
        "pixelvault.search", "pixelvault.gui", "pixelvault.utils",
        "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui",
        "PIL", "cv2", "numpy", "sklearn", "cachetools",
    ]

    if ONNX_MODELS_DIR.exists():
        onnx_files = list(ONNX_MODELS_DIR.glob("*.onnx"))
        if onnx_files:
            datas.append((str(ONNX_MODELS_DIR), "models"))
            print(f"Including {len(onnx_files)} ONNX model files")

    datas_str = ""
    for src, dst in datas:
        datas_str += f"('{src}', '{dst}'),"

    hidden_str = "".join(f"'{imp}'," for imp in hiddenimports)

    icon_arg = f"icon='{ICON_PATH}'" if ICON_PATH.exists() else ""

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
from PySide6 import QtCore

block_cipher = None

a = analysis(
    ['{ROOT_DIR / "pixelvault" / "__main__.py"}'],
    pathex=['{ROOT_DIR}'],
    binaries=[],
    datas=[{datas_str}],
    hiddenimports=[{hidden_str}],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    {icon_arg}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='{APP_NAME}',
)
"""
    spec_path = ROOT_DIR / f"{APP_NAME}.spec"
    spec_path.write_text(spec_content, encoding="utf-8")
    print(f"Spec file generated: {spec_path}")
    return spec_path


def build():
    if not check_dependencies():
        sys.exit(1)

    spec_path = build_spec()

    print("Starting PyInstaller build...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_path), "--clean", "--noconfirm"],
        cwd=str(ROOT_DIR),
    )

    if result.returncode == 0:
        print(f"\nBuild successful! Output in: {ROOT_DIR / 'dist' / APP_NAME}")
    else:
        print(f"\nBuild failed with return code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
