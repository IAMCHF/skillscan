"""
HTML 审核报告渲染器 — SkillHub 风格
"""
from __future__ import annotations
import os
from jinja2 import Template
from app.models.schemas import SkillScanResult, TRACE_DISPLAY, TRACE_LETTER, TRACE_COLORS, TRACE_SUB_INDICATORS

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

def render_html_report(result: SkillScanResult) -> str:
    """渲染单个技能 TRACE 审核报告 HTML"""
    template_path = os.path.join(_TEMPLATE_DIR, "report.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    # 构建模板所需的所有变量
    dim_data = []
    for ds in result.trace_scores:
        sub_config = TRACE_SUB_INDICATORS.get(ds.dimension, [])
        sub_items = []
        for sub in sub_config:
            found = next((s for s in ds.sub_indicators if s.key == sub["key"]), None)
            score = found.score if found else 0
            comment = found.comment if found else ""
            sub_items.append({"key": sub["key"], "name": sub["name"], "desc": sub["desc"], "score": score, "comment": comment})
        
        max_subs = max((s.score for s in ds.sub_indicators), default=3)
        min_subs = min((s.score for s in ds.sub_indicators), default=3)
        dim_data.append({
            "key": ds.dimension, "letter": ds.letter,
            "display": ds.display_name, "score": ds.score,
            "color": TRACE_COLORS.get(ds.dimension, "#3b82f6"),
            "summary": ds.findings_summary,
            "subs": sub_items,
            "max_sub_score": max_subs, "min_sub_score": min_subs,
        })

    # 星级文字
    star_count = round(result.overall_score)
    if result.overall_score >= 4.5: rating_text = "优秀"
    elif result.overall_score >= 3.5: rating_text = "良好"
    elif result.overall_score >= 2.5: rating_text = "一般"
    else: rating_text = "需改进"

    return template.render(
        result=result,
        dim_data=dim_data,
        trace_display=TRACE_DISPLAY,
        trace_colors=TRACE_COLORS,
        star_count=star_count,
        rating_text=rating_text,
        enumerate=enumerate, round=round, len=len, min=min, max=max, zip=zip, list=list,
    )
