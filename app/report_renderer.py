"""
HTML 审核报告渲染器 — SkillHub 严格复刻风格
"""
from __future__ import annotations
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
        rating_text=rating_text,
        rating_cls=rating_cls,
        _fmt_num=_fmt_num,
        _fmt_duration=_fmt_duration,
    )
