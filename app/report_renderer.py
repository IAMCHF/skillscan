"""
HTML 审核报告渲染器 — SkillHub 严格复刻风格
"""
from __future__ import annotations
import math
import os
from jinja2 import Template
from app.models.schemas import SkillScanResult, TRACE_COLORS, TRACE_SUB_INDICATORS

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _fmt_num(n: int) -> str:
    """数字格式化 — 10000+ → 万"""
    if n >= 10000:
        w = n / 10000
        return f"{w:.1f} 万" if w < 10 else f"{int(w)} 万"
    return str(n)


def _fmt_duration(ms: int) -> str:
    """毫秒格式化"""
    if ms >= 1000:
        return f"{ms / 1000:.1f} s"
    return f"{ms} ms"


def _compute_pentagon(dim_data: list[dict]) -> dict:
    """计算 TRACE 五边形雷达图 SVG 坐标

    五边形顶点顺序（从顶部顺时针）：
    T(可信任度) → R(可靠性) → A(适用性) → C(规范性) → E(有效性)
    """
    cx, cy = 200, 215
    max_r = 150
    # 5 个顶点角度（从顶部顺时针，SVG 坐标系 y 向下）
    angles_deg = [90, 162, 234, 306, 18]

    def _point(angle_deg: float, radius: float) -> tuple[float, float]:
        rad = math.radians(angle_deg)
        x = cx + radius * math.cos(rad)
        y = cy - radius * math.sin(rad)
        return round(x, 1), round(y, 1)

    # 5 层网格（评分 1-5）
    grids = []
    for level in range(1, 6):
        r = max_r * level / 5
        pts = " ".join(f"{_point(a, r)[0]},{_point(a, r)[1]}" for a in angles_deg)
        grids.append({"level": level, "points": pts})

    # 实际评分的多边形顶点
    score_points = []
    for i, dim in enumerate(dim_data):
        score = max(0, min(5, dim["score"]))
        r = max_r * score / 5 if score > 0 else 2
        x, y = _point(angles_deg[i], r)
        score_points.append(f"{x},{y}")

    # 顶点标签（在最大五边形外侧）
    label_offset = 26
    vertices = []
    for i, dim in enumerate(dim_data):
        angle = angles_deg[i]
        score = dim["score"]
        x, y = _point(angle, max_r)
        lx, ly = _point(angle, max_r + label_offset)
        # 分数文字位置（稍微内缩）
        sx, sy = _point(angle, max(score / 5 * max_r + 18, 22))
        # 调整水平居中
        if angle == 90:
            lx, sx = cx, lx
        elif angle == 18:
            lx += 4
            sx = lx
        elif angle == 162:
            lx -= 4
            sx = lx
        elif angle in (234, 306):
            sx = lx
        vertices.append({
            "x": x, "y": y, "lx": lx, "ly": ly,
            "sx": sx, "sy": sy,
            "letter": dim["letter"], "name": dim["display"],
            "score": f"{score:.1f}", "color": dim["color"],
        })

    return {
        "grids": grids,
        "score_points": " ".join(score_points),
        "vertices": vertices,
        "cx": cx, "cy": cy, "max_r": max_r,
    }


def render_html_report(result: SkillScanResult) -> str:
    """渲染单个技能 TRACE 审核报告 HTML（SkillHub 风格）"""
    template_path = os.path.join(_TEMPLATE_DIR, "report.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    # 评级
    score = result.overall_score or 0
    if score >= 4.5:
        rating_text = "优秀"
        rating_cls = "rating-excellent"
    elif score >= 3.5:
        rating_text = "良好"
        rating_cls = "rating-good"
    elif score >= 2.5:
        rating_text = "一般"
        rating_cls = "rating-average"
    else:
        rating_text = "需改进"
        rating_cls = "rating-poor"

    # 维度数据
    dim_data = []
    for ds in result.trace_scores:
        sub_config = TRACE_SUB_INDICATORS.get(ds.dimension, [])
        sub_items = []
        for sub in sub_config:
            found = next((s for s in ds.sub_indicators if s.key == sub["key"]), None)
            sub_items.append({
                "key": sub["key"], "name": sub["name"], "desc": sub["desc"],
                "score": found.score if found else 0,
                "comment": found.comment if found else "",
            })

        dim_data.append({
            "key": ds.dimension, "letter": ds.letter,
            "display": ds.display_name, "score": ds.score,
            "color": TRACE_COLORS.get(ds.dimension, "#3b82f6"),
            "summary": ds.findings_summary,
            "subs": sub_items,
        })

    return template.render(
        result=result,
        dim_data=dim_data,
        pentagon=_compute_pentagon(dim_data),
        rating_text=rating_text,
        rating_cls=rating_cls,
        stars=result.stars or 0,
        _fmt_num=_fmt_num,
        _fmt_duration=_fmt_duration,
    )
