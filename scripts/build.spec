# -*- mode: python ; coding: utf-8 -*-
"""
PointVault PyInstaller 打包配置
用法:
    pip install pyinstaller
    pyinstaller scripts/build.spec --clean --noconfirm

打包后输出在 dist/PointVault/ 目录下
"""
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集所有点云库的子模块（防止动态导入遗漏）
hiddenimports = []
hiddenimports += collect_submodules('open3d')
hiddenimports += collect_submodules('laspy')
hiddenimports += collect_submodules('sqlalchemy')
hiddenimports += collect_submodules('scipy')
hiddenimports += collect_submodules('sklearn')
hiddenimports += collect_submodules('matplotlib')
hiddenimports += collect_submodules('qt_material')
hiddenimports += [
    'plyfile', 'pypcd4', 'cachetools', 'tqdm',
    'numpy.core._multiarray_umath', 'numpy.random.common',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
]

# 收集数据文件：qt-material 主题 XML、matplotlib 字体等
datas = []
datas += collect_data_files('qt_material', include_py_files=False)
datas += collect_data_files('matplotlib')
# 把 pointvault 包整体复制（包含 resources / 标准标签集）
datas += [('pointvault', 'pointvault')]

# 动态库：Open3D 自带大量 .so/.dll
binaries = []

a = Analysis(
    ['pointvault/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 排除 Qt Web 系列（体积大，用不到）
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
        'PySide6.QtQuick', 'PySide6.QtQuick3D',
        # 排除科学计算中的不常用部分
        'scipy.spatial.cKDTree.tests', 'IPython', 'notebook',
    ],
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
    name='PointVault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # GUI 程序不显示控制台
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='resources/icons/app_icon.ico'   # TODO: 替换为实际图标路径
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PointVault',
)
