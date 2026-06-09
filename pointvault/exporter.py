"""
导出模块
- 带标签点云导出（PLY/LAS/PCD）
- 语义分割数据集格式导出（KITTI, S3DIS 标准）
- 项目报告导出（HTML/PDF 包含统计图表、缩略图）
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from pointvault.constants import UNLABELED_ID
from pointvault.db.models import Annotation, LabelDefinition, LabelSet, PointCloud
from pointvault.io.container import PointCloudData
from pointvault.io.label_file import read_labels, compute_label_histogram
from pointvault.io.writer import PointCloudWriter

logger = logging.getLogger(__name__)

_writer = PointCloudWriter()


# ============================================================
# 1. 带标签的点云导出
# ============================================================
def export_labeled_pointcloud(
    pc_data: PointCloudData,
    labels: np.ndarray,
    output_path: Path | str,
    label_map: Optional[Dict[int, LabelDefinition]] = None,
    use_label_color: bool = True,
    format: Optional[str] = None,
) -> Path:
    """
    导出带标签的点云

    - PLY: 额外写 label 字段 (int32)
    - LAS: 写入 classification + 扩展 label_id 字段
    - 如果 use_label_color=True，颜色来自标签色而非原始 RGB
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = np.asarray(labels, dtype=np.int32).ravel()
    if labels.size != pc_data.num_points:
        raise ValueError(f"标签长度 {labels.size} 与点数 {pc_data.num_points} 不匹配")

    merged = PointCloudData(
        points=pc_data.points.copy(),
        colors=pc_data.colors.copy() if pc_data.has_colors() else None,
        normals=pc_data.normals.copy() if pc_data.has_normals() else None,
        intensity=pc_data.intensity.copy() if pc_data.has_intensity() else None,
        labels=labels.copy(),
    )

    if use_label_color and label_map is not None:
        colors = np.zeros((merged.num_points, 3), dtype=np.float32)
        colors[:, 0] = 0.5
        colors[:, 1] = 0.5
        colors[:, 2] = 0.5
        for lid, ld in label_map.items():
            if lid == UNLABELED_ID:
                continue
            m = labels == lid
            colors[m, 0] = ld.color_float[0]
            colors[m, 1] = ld.color_float[1]
            colors[m, 2] = ld.color_float[2]
        merged.colors = colors

    return _writer.write(merged, output_path, format=format)


# ============================================================
# 2. 语义分割数据集导出
# ============================================================
@dataclass
class DatasetExportConfig:
    output_dir: Path
    pointcloud_format: str = ".ply"
    label_extension: str = ".label"
    split_ratio: Optional[Tuple[float, float, float]] = None  # train/val/test
    dataset_name: str = "pointvault_dataset"


def export_semantic_dataset(
    items: List[Tuple[PointCloud, PointCloudData, Annotation, LabelSet]],
    config: DatasetExportConfig,
) -> Tuple[Path, Dict[str, Any]]:
    """
    导出为标准语义分割数据集：
    <output_dir>/
        dataset.json
        classes.txt      # label_id -> 名称映射
        points/
            <name>.<fmt>
        labels/
            <name>.label
        splits/
            train.txt / val.txt / test.txt
    """
    out = Path(config.output_dir)
    points_dir = out / "points"
    labels_dir = out / "labels"
    splits_dir = out / "splits"
    points_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    # 写 classes.txt（使用第一个标签集）
    label_defs: List[LabelDefinition] = []
    ls_by_id: Dict[int, LabelDefinition] = {}
    if items:
        _, _, _, ls = items[0]
        label_defs = list(ls.labels)
        ls_by_id = {ld.label_id: ld for ld in label_defs}
    with open(out / "classes.txt", "w", encoding="utf-8") as f:
        for ld in label_defs:
            f.write(f"{ld.label_id} {ld.name}\n")

    stats: Dict[str, Any] = {
        "dataset_name": config.dataset_name,
        "export_time": datetime.utcnow().isoformat(),
        "num_samples": len(items),
        "classes": [
            {
                "id": ld.label_id,
                "name": ld.name,
                "color": list(ld.color),
            }
            for ld in label_defs
        ],
        "samples": [],
    }

    names: List[str] = []
    for i, (pc_meta, pc_data, annot, labelset) in enumerate(items):
        name = f"{pc_meta.name}_{i}" if False else pc_meta.name
        # 确保文件名安全
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(name).stem)
        safe_name = safe_name or f"sample_{i:05d}"
        names.append(safe_name)

        pc_path = points_dir / f"{safe_name}{config.pointcloud_format}"
        lab_path = labels_dir / f"{safe_name}{config.label_extension}"

        # 导出点云（不覆盖颜色，保持原始）
        _writer.write(pc_data, pc_path)

        # 导出标签（int32 二进制，与点云等长）
        labels = read_labels(annot.label_file_path)
        if labels.size != pc_data.num_points:
            logger.warning(f"标签长度 {labels.size} 与点数 {pc_data.num_points} 不一致，填充")
            padded = np.zeros(pc_data.num_points, dtype=np.int32)
            n = min(labels.size, pc_data.num_points)
            padded[:n] = labels[:n]
            labels = padded
        labels.astype(np.int32).tofile(lab_path)

        hist = compute_label_histogram(annot.label_file_path)
        stats["samples"].append(
            {
                "name": safe_name,
                "pointcloud_file": f"points/{pc_path.name}",
                "label_file": f"labels/{lab_path.name}",
                "num_points": pc_data.num_points,
                "label_histogram": {str(k): v for k, v in hist.items()},
            }
        )

    # 数据集元信息
    with open(out / "dataset.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    # 数据集划分
    if config.split_ratio is not None:
        tr, va, te = config.split_ratio
        tr = max(0.0, float(tr))
        va = max(0.0, float(va))
        te = max(0.0, float(te))
        s = tr + va + te
        if s <= 0:
            tr = 1.0
            s = 1.0
        tr = tr / s
        va = va / s
        te = te / s
        rng = np.random.default_rng(42)
        idx = rng.permutation(len(names))
        n_train = int(tr * len(names))
        n_val = int(va * len(names))
        train_set = [names[i] for i in idx[:n_train]]
        val_set = [names[i] for i in idx[n_train : n_train + n_val]]
        test_set = [names[i] for i in idx[n_train + n_val :]]
        with open(splits_dir / "train.txt", "w") as f:
            f.write("\n".join(train_set))
        with open(splits_dir / "val.txt", "w") as f:
            f.write("\n".join(val_set))
        with open(splits_dir / "test.txt", "w") as f:
            f.write("\n".join(test_set))

    return out, stats


# ============================================================
# 3. 项目报告导出
# ============================================================
def generate_project_report_html(
    project_name: str,
    pointclouds: List[PointCloud],
    annotations: List[Annotation],
    label_map: Dict[int, LabelDefinition],
    output_path: Path | str,
    thumbnail_paths: Optional[Dict[int, str]] = None,
) -> Path:
    """
    生成 HTML 项目报告，包含：
    - 项目基本信息
    - 点云清单（缩略图 + 元数据）
    - 标注统计饼图/柱状图（matplotlib 生成 SVG 内嵌）
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError("导出报告需要 matplotlib")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 统计总标签分布
    total_hist: Dict[int, int] = {}
    for a in annotations:
        try:
            h = compute_label_histogram(a.label_file_path)
            for k, v in h.items():
                total_hist[int(k)] = total_hist.get(int(k), 0) + v
        except Exception:
            pass

    # 生成图表（SVG）
    svg_charts: Dict[str, str] = {}
    if total_hist:
        ids = sorted(total_hist.keys())
        values = [total_hist[k] for k in ids]
        labels_text = []
        colors_list = []
        for lid in ids:
            if lid == UNLABELED_ID:
                labels_text.append(f"未标注 #{lid}")
                colors_list.append("#888888")
            else:
                ld = label_map.get(lid)
                if ld is not None:
                    labels_text.append(f"{ld.name} #{lid}")
                    colors_list.append(f"#{ld.color_r:02x}{ld.color_g:02x}{ld.color_b:02x}")
                else:
                    labels_text.append(f"未定义 #{lid}")
                    colors_list.append("#cccccc")

        # 饼图
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(values, labels=labels_text, colors=colors_list, autopct="%1.1f%%", startangle=90)
            ax.set_title(f"标注分布（总点数: {sum(values):,}）")
            ax.axis("equal")
            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
                fig.savefig(tf.name, format="svg", bbox_inches="tight")
                tfp = tf.name
            plt.close(fig)
            with open(tfp, "r", encoding="utf-8", errors="ignore") as f:
                svg_charts["pie"] = f.read()
            try:
                os.unlink(tfp)
            except OSError:
                pass
        except Exception as e:
            logger.warning(f"生成饼图失败: {e}")
            svg_charts["pie"] = f"<p>图表生成失败: {e}</p>"

        # 柱状图
        try:
            fig, ax = plt.subplots(figsize=(10, 5))
            x_pos = list(range(len(ids)))
            bars = ax.bar(x_pos, values, color=colors_list)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels_text, rotation=45, ha="right")
            ax.set_ylabel("点数量")
            ax.set_title("各标签点数量")
            ax.grid(axis="y", linestyle="--", alpha=0.5)
            for bar, v in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{v:,}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
            fig.tight_layout()
            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
                fig.savefig(tf.name, format="svg", bbox_inches="tight")
                tfp = tf.name
            plt.close(fig)
            with open(tfp, "r", encoding="utf-8", errors="ignore") as f:
                svg_charts["bar"] = f.read()
            try:
                os.unlink(tfp)
            except OSError:
                pass
        except Exception as e:
            logger.warning(f"生成柱状图失败: {e}")
            svg_charts["bar"] = f"<p>图表生成失败: {e}</p>"

    # 组装 HTML
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    pc_rows_html = ""
    for i, pc in enumerate(pointclouds):
        thumb = ""
        if thumbnail_paths and pc.id in thumbnail_paths:
            thumb_p = Path(thumbnail_paths[pc.id])
            if thumb_p.exists():
                # 转为 base64 内嵌
                import base64
                try:
                    with open(thumb_p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    suffix = thumb_p.suffix.lstrip(".")
                    thumb = f'<img src="data:image/{suffix};base64,{b64}" width="200" />'
                except Exception:
                    pass
        total_pts = pc.num_points
        labeled = 0
        annot = next((a for a in annotations if a.pointcloud_id == pc.id), None)
        if annot is not None:
            labeled = annot.total_labeled
        pc_rows_html += f"""
        <tr>
            <td style="padding:8px">{thumb or '(无缩略图)'}</td>
            <td style="padding:8px">{pc.name}</td>
            <td style="padding:8px">{pc.file_format}</td>
            <td style="padding:8px;text-align:right">{total_pts:,}</td>
            <td style="padding:8px;text-align:right">{labeled:,} ({100.0*labeled/max(1,total_pts):.1f}%)</td>
            <td style="padding:8px;font-size:80%;opacity:0.7">{pc.min_x:.2f},{pc.min_y:.2f},{pc.min_z:.2f} ~ {pc.max_x:.2f},{pc.max_y:.2f},{pc.max_z:.2f}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>PointVault 项目报告 - {project_name}</title>
<style>
    body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; max-width: 1200px; margin: 32px auto; padding: 0 16px; color: #222; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
    h2 {{ margin-top: 32px; color: #2a6; border-left: 4px solid #2a6; padding-left: 12px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #ddd; vertical-align: middle; }}
    th {{ background: #f2f2f2; padding: 10px; text-align: left; }}
    .chart-container {{ margin: 16px 0; background: #fafafa; padding: 16px; border-radius: 8px; }}
    .meta {{ display: flex; gap: 32px; margin: 16px 0; }}
    .meta div {{ background: #eef6ff; padding: 12px 20px; border-radius: 8px; }}
    .footer {{ margin-top: 48px; color: #999; font-size: 80%; text-align: right; }}
</style>
</head>
<body>
<h1>📊 PointVault 项目报告</h1>
<h2>项目概览</h2>
<div class="meta">
    <div><strong>项目名称</strong><br/>{project_name}</div>
    <div><strong>点云数量</strong><br/>{len(pointclouds)} 个</div>
    <div><strong>标签类别数</strong><br/>{max(0, len([k for k in label_map if k != UNLABELED_ID]))} 类</div>
    <div><strong>总点数</strong><br/>{sum(pc.num_points for pc in pointclouds):,}</div>
</div>
<div><strong>生成时间：</strong>{now}</div>

<h2>点云清单</h2>
<table>
<thead><tr>
    <th style="width:220px">缩略图</th>
    <th>名称</th>
    <th>格式</th>
    <th style="width:120px">点数</th>
    <th style="width:160px">已标注</th>
    <th>坐标范围 (min~max)</th>
</tr></thead>
<tbody>
{pc_rows_html or '<tr><td colspan="6" style="text-align:center;padding:24px;color:#999">暂无点云数据</td></tr>'}
</tbody>
</table>

<h2>标注统计</h2>
<div class="chart-container">
    <h3>饼图分布</h3>
    {svg_charts.get('pie', '<p>无数据</p>')}
</div>
<div class="chart-container">
    <h3>柱状图对比</h3>
    {svg_charts.get('bar', '<p>无数据</p>')}
</div>

<h2>标签定义</h2>
<table>
<thead><tr><th>ID</th><th>名称</th><th>颜色</th><th>总点数</th></tr></thead>
<tbody>
{''.join(
    f'<tr><td style="padding:8px">{lid}</td><td style="padding:8px">{ld.name}</td><td style="padding:8px"><span style="display:inline-block;width:24px;height:24px;background:rgb{ld.color};border:1px solid #000;vertical-align:middle"></span> rgb{ld.color}</td><td style="padding:8px;text-align:right">{total_hist.get(lid, 0):,}</td></tr>'
    for lid, ld in sorted(label_map.items())
) if label_map else '<tr><td colspan="4" style="text-align:center;color:#999;padding:16px">无标签定义</td></tr>'}
</tbody>
</table>

<div class="footer">
    由 PointVault {datetime.utcnow().year} 自动生成 · {now}
</div>
</body>
</html>
"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out
