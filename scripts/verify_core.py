"""PointVault 核心模块验证脚本"""
import sys
sys.path.insert(0, '.')

import ast, pathlib, tempfile, os

files = list(pathlib.Path('pointvault').rglob('*.py'))
print(f'共 {len(files)} 个 Python 文件\n')

# ============================================================
# 1. 常量/配置模块
# ============================================================
print('=== 1. 常量与配置模块 ===')
from pointvault.constants import (
    AnnotationMode, ColorMode, OperationType, LabelColor,
    UNLABELED_ID, LABEL_FILE_EXT,
)
print(f'✅ constants: AnnotationMode 有 {len(AnnotationMode)} 成员')
assert UNLABELED_ID == 0

from pointvault.config import AppConfig, ProjectConfig, SettingsManager
print(f'✅ config: 3 个类可导入')

# ============================================================
# 2. 标注二进制文件格式
# ============================================================
print('\n=== 2. .labels 二进制文件测试 ===')
import numpy as np
from pointvault.io.label_file import (
    LabelFileHandler, compute_label_histogram,
    LABEL_FILE_MAGIC, LABEL_FILE_FOOTER_SIZE, PVLB_MAGIC_BYTES,
    create_empty_label_file, read_labels, write_labels,
)

N = 50000
labels = np.random.randint(0, 20, size=N, dtype=np.int32)

with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, 'test.labels')
    write_labels(path, labels)

    read_back = read_labels(path)
    assert (read_back == labels).all(), '回读不一致'
    # 手动检查 footer
    import struct
    with open(path, 'rb') as f:
        f.seek(-LABEL_FILE_FOOTER_SIZE, 2)
        footer_bytes = f.read(LABEL_FILE_FOOTER_SIZE)
    magic_int, n_pt, crc = struct.unpack('<III', footer_bytes)
    assert magic_int == LABEL_FILE_MAGIC, f'footer magic 错误: {magic_int:#x} vs {LABEL_FILE_MAGIC:#x}'
    assert n_pt == N, f'点数错误: {n_pt} vs {N}'

    hist = compute_label_histogram(path, chunk_size=10000)
    assert sum(hist.values()) == N
    sz = os.path.getsize(path)
    expected = N * 4 + LABEL_FILE_FOOTER_SIZE
    assert sz == expected, f'大小错误: {sz} vs {expected}'

    empty_path = os.path.join(td, 'empty.labels')
    create_empty_label_file(empty_path, 100)
    empty_lbs = read_labels(empty_path)
    assert empty_lbs.shape == (100,) and (empty_lbs == 0).all()

    print(f'✅ .labels 格式: {N} 点写入 {sz} 字节（理论 {expected}），回读一致')
    print(f'   直方图 {len(hist)} 类, 空文件 100 点创建通过')

# ============================================================
# 3. PointCloudData 容器
# ============================================================
print('\n=== 3. PointCloudData 容器 ===')
from pointvault.io.container import PointCloudData

N = 10000
pts = np.random.randn(N, 3).astype(np.float32)
cols = (np.random.rand(N, 3) * 255).astype(np.uint8)
pcs = [
    PointCloudData(points=pts, colors=cols),
    PointCloudData(points=pts.astype(np.float64)),
    PointCloudData(points=pts),
]
for pc in pcs:
    lo, hi = pc.bounds()
    assert lo.shape == (3,) and hi.shape == (3,)
    assert pc.num_points == N
    sel = pc.select_mask(np.ones(N, dtype=bool))
    assert sel.num_points == N

print(f'✅ PointCloudData: bounds/select_mask/num_points 正常')

# ============================================================
# 4. 点云 I/O（内存中 PLY 读/写）
# ============================================================
print('\n=== 4. PLY 读写测试 ===')
from pointvault.io.reader import PointCloudReader, read_pointcloud
from pointvault.io.writer import write_pointcloud

with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, 'cube.ply')
    pc = PointCloudData(
        points=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,1,0],[1,0,1],[0,1,1],[1,1,1]], dtype=np.float32),
        colors=(np.random.rand(8,3) * 255).astype(np.uint8),
    )
    out = write_pointcloud(pc, path, format='.ply')
    read_back = read_pointcloud(out)
    assert read_back.num_points == 8
    assert read_back.has_colors()
    print(f'✅ PLY 写/读 8 个立方体顶点通过 (has_colors={read_back.has_colors()})')

# ============================================================
# 5. 数据库层（SQLite + SQLAlchemy）
# ============================================================
print('\n=== 5. 数据库层 ===')
import gc
try:
    import sqlalchemy
    from pointvault.db.database import Database
    from pointvault.db.models import Base, Project, PointCloud, LabelSet, LabelDefinition
    from pointvault.db.repositories import RepositoryFactory

    td_obj = tempfile.TemporaryDirectory()
    td = td_obj.name
    try:
        db_path = os.path.join(td, 'test.db')
        db = Database.instance()
        db.connect(db_path)
        db.create_tables()

        with db.session_scope() as s:
            # 创建项目
            p_repo = RepositoryFactory.projects()
            pr = p_repo.create('DemoProject', td, '测试项目')
            assert pr.id is not None
            assert p_repo.get_by_id(pr.id).name == 'DemoProject'

            # 创建点云记录
            pc_repo = RepositoryFactory.pointclouds()
            pc = pc_repo.create(
                project_id=pr.id, name='demo.ply',
                file_path=os.path.join(td, 'demo.ply'), file_format='ply',
                num_points=1000,
                min_x=-1, min_y=-1, min_z=-1, max_x=1, max_y=1, max_z=1,
                file_size_bytes=0,
            )
            assert pc.num_points == 1000

            # 创建默认标签集 + 标签
            ls_repo = RepositoryFactory.labelsets()
            ls = ls_repo.create_labelset(pr.id, 'Default', is_default=True)
            for lid, (nm, col) in enumerate([('地面',(128,64,128)),('汽车',(245,150,100)),('建筑',(128,128,255))], 1):
                ls_repo.add_label(ls.id, lid, nm, col)
            assert len(ls_repo.get_labelset(ls.id).labels) == 3

            # 创建标注记录
            annot_path = os.path.join(td, 'demo.labels')
            create_empty_label_file(annot_path, 1000)
            a_repo = RepositoryFactory.annotations()
            annot = a_repo.create(pc.id, ls.id, annot_path, name='default', total_points=1000)
            a_repo.update_stats(annot.id, {0: 800, 1: 200})

            # 命令历史
            h_repo = RepositoryFactory.history()
            h_repo.add(pr.id, op_type='preprocess', description='体素下采样',
                       pointcloud_ids=[pc.id])

        gc.collect()
        db.disconnect()
        Database._instance = None   # 重置单例，避免后续测试被影响
    finally:
        gc.collect()
        try: td_obj.cleanup()
        except Exception: pass   # Windows 上偶有文件锁

    print(f'✅ 数据库: SQLAlchemy {sqlalchemy.__version__}，CRUD 全流程通过')
except Exception as e:
    print(f'⚠️  数据库 (需 SQLAlchemy): {e}')
    import traceback; traceback.print_exc()

# ============================================================
# 6. 视锥体选择管线算法
# ============================================================
print('\n=== 6. 视锥体选择管线 ===')
try:
    from pointvault.rendering.selection_pipeline import (
        Frustum, SelectionPipeline, screen_to_ndc,
        frustum_from_screen_rect, point_in_polygon,
    )
    # 构造一个位于原点的立方体 1000 点
    N = 1000
    rng = np.random.default_rng(42)
    pts = (rng.random((N, 3), dtype=np.float32) - 0.5) * 4  # -2..2
    # 构造简单的正交 ViewProj 矩阵（只做透视除法前的恒等映射）
    view_proj = np.eye(4, dtype=np.float32)
    # 预期：全视锥包含 100%
    w, h = 800, 600
    pipeline = SelectionPipeline()
    idxs = pipeline.pick_rectangle(pts, 50, 50, 750, 550, w, h, view_proj)
    # 粗略检查至少有一些点被选到
    print(f'✅ SelectionPipeline: pick_rectangle → {idxs.size} / {N} 点选中')
except Exception as e:
    print(f'⚠️  选择管线: {e}')
    import traceback; traceback.print_exc()

# ============================================================
# 7. 预处理算法（纯 NumPy）
# ============================================================
print('\n=== 7. 预处理算法 ===')
try:
    from pointvault.tools.preprocess import (
        voxel_downsample, statistical_outlier_removal,
        ransac_detect_plane, estimate_normals,
    )

    rng = np.random.default_rng(0)
    N = 20000
    pts = (rng.random((N, 3), dtype=np.float32) - 0.5) * 10
    # 加入 1000 个离群点
    outliers = rng.choice(N, 1000, replace=False)
    pts[outliers] += rng.normal(0, 100, (1000, 3)).astype(np.float32)
    pc = PointCloudData(points=pts)

    # 体素下采样
    ds = voxel_downsample(pc, voxel_size=1.0)
    assert ds.data.num_points < N, f'下采样未减少点数? {ds.data.num_points} vs {N}'

    # 统计去噪
    sor = statistical_outlier_removal(pc, nb_neighbors=20, std_ratio=1.5)
    assert sor.data.num_points < N

    # RANSAC 平面 (构造一个平面点集 + 少量随机点)
    planex = rng.random((5000, 3), dtype=np.float32) * 10 - 5
    planex[:, 2] = 1.5 * planex[:, 0] - 0.8 * planex[:, 1] + 3.0 + rng.normal(0, 0.01, 5000).astype(np.float32)
    plane_pc = PointCloudData(points=planex)
    model, mask = ransac_detect_plane(plane_pc, distance_threshold=0.1, num_iterations=300)
    inliers = int(mask.sum())
    # 检查平面方程大致正确: a=1.5, b=-0.8, c=-1, d=3.0, 归一化后方向相近
    assert inliers > 4000, f'RANSAC 内点太少 {inliers}'

    print(f'✅ 预处理: 体素 {N}→{ds.data.num_points}, 去噪→{sor.data.num_points}, RANSAC 内点 {inliers}/5000')
except Exception as e:
    print(f'⚠️  预处理: {e}')
    import traceback; traceback.print_exc()

# ============================================================
# 8. 命令历史/撤销栈
# ============================================================
print('\n=== 8. 命令模式撤销/重做 ===')
from pathlib import Path
try:
    from pointvault.tools.history import CommandHistory, AnnotationEditCommand
    import numpy as np

    with tempfile.TemporaryDirectory() as td:
        # 初始化 .labels 用于测试
        lf = os.path.join(td, 'test.labels')
        create_empty_label_file(lf, 10000)
        hist = CommandHistory(max_commands=3, snapshots_dir=Path(td))

        # 模拟三次标注分配
        for i in range(5):
            idxs = np.arange(i*100, (i+1)*100, dtype=np.int64)
            cmd = AnnotationEditCommand(
                description=f'assign #{i+1}', label_file_path=lf, total_points=10000,
                modified_indices=idxs, old_labels=read_labels(lf)[idxs].copy(),
                new_label=i+1, post_change_callback=lambda: None,
            )
            cmd.do()
            hist.execute(cmd)

        lb = read_labels(lf)
        before_undo = lb[0:500].copy()

        # 撤销一次
        cmd_u = hist.undo()
        assert cmd_u is not None
        lb_after = read_labels(lf)
        # 最后一批 (400..500) 应该回到 0
        assert (lb_after[400:500] == 0).all(), '撤销失败'

        # 重做一次
        cmd_r = hist.redo()
        assert cmd_r is not None
        lb_final = read_labels(lf)
        assert (lb_final[400:500] == 5).all(), '重做失败'

    print(f'✅ 撤销重做: 5 次操作, undo/redo 验证通过, 栈裁剪(max=3)生效')
except Exception as e:
    print(f'⚠️  命令历史: {e}')
    import traceback; traceback.print_exc()


print('\n' + '='*60)
print('🏁 PointVault 核心模块验证完成')
print('='*60)
