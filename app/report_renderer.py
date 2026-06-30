"""
HTML 审核报告渲染器 — Jinja2 模板引擎
"""
from __future__ import annotations

import os
import time
import glob as glob_mod

from jinja2 import Template

from app.models.schemas import (
    ReportContext, DIMENSION_DISPLAY, DIMENSION_ICONS, RiskLevel,
)

# 模板目录
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def render_html_report(context: ReportContext) -> str:
    """渲染完整 HTML 审核报告"""
    template_path = os.path.join(_TEMPLATE_DIR, "report.html")
    if not os.path.exists(template_path):
        # 内联后备模板
        return _render_inline_report(context)

    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.render(
        ctx=context,
        dim_display=DIMENSION_DISPLAY,
        dim_icons=DIMENSION_ICONS,
        risk_display=RiskLevel.display,
        risk_color=RiskLevel.color,
        zip=zip, enumerate=enumerate, len=len,
        sorted=sorted, round=round, max=max, min=min,
    )


def cleanup_old_reports():
    """清理 24 小时前的旧报告"""
    import tempfile
    reports_dir = os.path.join(tempfile.gettempdir(), "skillscan_reports")
    cutoff = time.time() - 86400  # 24 hours

    for pattern in ["report_*.html"]:
        for f in glob_mod.glob(os.path.join(reports_dir, pattern)):
            if os.path.getmtime(f) < cutoff:
                try:
                    os.remove(f)
                except OSError:
                    pass


def _render_inline_report(context: ReportContext) -> str:
    """内嵌后备 HTML 报告模板（无需外部文件）"""
    report_html = _build_report_html(context)
    return report_html


def _build_report_html(ctx: ReportContext) -> str:
    """构建完整的 HTML 报告字符串"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SkillScan 审核报告 — {ctx.scan_id}</title>
<style>
/* ============================================================
   SkillScan Report Styles — 统一 HTML 审核报告样式
   ============================================================ */
:root {{
    --bg: #0f172a;
    --card-bg: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent: #3b82f6;
    --accent-light: #60a5fa;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --purple: #8b5cf6;
    --orange: #f97316;
    --radius: 8px;
    --radius-lg: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,.3);
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}

.container {{ max-width: 1280px; margin: 0 auto; padding: 24px 32px; }}

/* ── Header ── */
.report-header {{
    background: linear-gradient(135deg, #1e3a5f, #0f172a);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 32px 40px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}}
.report-header h1 {{ font-size: 26px; font-weight: 700; color: #fff; }}
.report-header .subtitle {{ color: var(--text-secondary); font-size: 14px; }}
.report-meta {{ text-align: right; }}
.report-meta .scan-id {{ font-family: "JetBrains Mono", monospace; font-size: 13px; color: var(--accent-light); }}
.report-meta .generated {{ font-size: 12px; color: var(--text-muted); }}

/* ── Stats Cards ── */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}}
.stat-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    text-align: center;
}}
.stat-card .stat-value {{ font-size: 32px; font-weight: 700; }}
.stat-card .stat-label {{ font-size: 13px; color: var(--text-secondary); margin-top: 4px; }}
.stat-card.total .stat-value {{ color: var(--accent-light); }}
.stat-card.passed .stat-value {{ color: var(--green); }}
.stat-card.conditional .stat-value {{ color: var(--yellow); }}
.stat-card.rejected .stat-value {{ color: var(--red); }}
.stat-card.avg-score .stat-value {{ color: var(--purple); }}

@media (max-width: 900px) {{
    .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
}}
@media (max-width: 600px) {{
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}

/* ── Section ── */
.section {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 28px 32px;
    margin-bottom: 20px;
}}
.section h2 {{
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section h2 .emoji {{ font-size: 20px; }}

/* ── Risk Distribution Bar ── */
.risk-bar-container {{
    display: flex;
    height: 32px;
    border-radius: var(--radius);
    overflow: hidden;
    margin-bottom: 12px;
}}
.risk-bar-segment {{ display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; color: #fff; }}
.risk-legend {{ display: flex; gap: 20px; flex-wrap: wrap; font-size: 13px; }}
.risk-legend span {{ display: flex; align-items: center; gap: 6px; }}
.risk-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}

/* ── Dimension Scores ── */
.dimension-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 20px;
}}
.dim-card {{
    background: rgba(255,255,255,.03);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 16px;
    text-align: center;
}}
.dim-card .dim-icon {{ font-size: 28px; margin-bottom: 8px; }}
.dim-card .dim-name {{ font-size: 13px; color: var(--text-secondary); font-weight: 600; }}
.dim-card .dim-score {{
    font-size: 36px;
    font-weight: 800;
    margin: 8px 0;
    line-height: 1;
}}
.dim-card .dim-max {{ font-size: 12px; color: var(--text-muted); }}
.dim-card .dim-bar-bg {{
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    margin-top: 8px;
    overflow: hidden;
}}
.dim-card .dim-bar-fill {{
    height: 100%;
    border-radius: 3px;
    transition: width .3s;
}}

@media (max-width: 900px) {{
    .dimension-grid {{ grid-template-columns: repeat(3, 1fr); }}
}}
@media (max-width: 500px) {{
    .dimension-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}

/* ── Tables ── */
.table-wrap {{ overflow-x: auto; }}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
table th {{
    background: rgba(255,255,255,.05);
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    color: var(--text-secondary);
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
}}
table td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
}}
table tr:hover td {{ background: rgba(255,255,255,.02); }}
table .slug-col {{ font-family: "JetBrains Mono", monospace; font-size: 12px; color: var(--accent-light); }}
table .name-col {{ font-weight: 500; }}
table .purpose-col {{ max-width: 200px; color: var(--text-secondary); font-size: 12px; }}
table .score-col {{ font-weight: 700; text-align: center; }}

/* ── Badges ── */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
}}
.badge-low {{ background: rgba(34,197,94,.15); color: var(--green); }}
.badge-medium {{ background: rgba(234,179,8,.15); color: var(--yellow); }}
.badge-high {{ background: rgba(239,68,68,.15); color: var(--red); }}
.badge-extreme {{ background: rgba(139,92,246,.15); color: var(--purple); }}
.badge-pass {{ background: rgba(34,197,94,.1); color: var(--green); }}
.badge-conditional {{ background: rgba(234,179,8,.1); color: var(--yellow); }}
.badge-reject {{ background: rgba(239,68,68,.1); color: var(--red); }}
.badge-rule {{ font-family: "JetBrains Mono", monospace; background: rgba(139,92,246,.15); color: var(--purple); }}

/* ── Red Flag Detail ── */
.flag-item {{
    background: rgba(239,68,68,.05);
    border-left: 3px solid var(--red);
    padding: 10px 14px;
    margin-bottom: 8px;
    border-radius: 0 var(--radius) var(--radius) 0;
}}
.flag-item .flag-rule {{ font-weight: 600; font-size: 13px; }}
.flag-item .flag-file {{ font-size: 11px; color: var(--text-muted); font-family: "JetBrains Mono", monospace; }}
.flag-item .flag-content {{
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    color: var(--text-secondary);
    background: rgba(0,0,0,.3);
    padding: 6px 8px;
    border-radius: 4px;
    margin-top: 6px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
}}

/* ── Footer ── */
.report-footer {{
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border);
    margin-top: 24px;
}}

/* ── Category Summary ── */
.cat-chip {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    background: rgba(59,130,246,.1);
    color: var(--accent-light);
    margin: 2px;
}}

/* ── Collapsible ── */
.collapsible-toggle {{
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--accent-light);
    font-size: 13px;
    padding: 4px 0;
}}
.collapsible-toggle:hover {{ opacity: .8; }}
.collapsible-content {{ margin-top: 12px; }}

.empty-state {{
    text-align: center;
    padding: 32px;
    color: var(--text-muted);
    font-size: 14px;
}}
</style>
</head>
<body>
<div class="container">

<!-- ═══════════ HEADER ═══════════ -->
<header class="report-header">
    <div>
        <h1>🛡️ SkillScan 技能安全审核报告</h1>
        <div class="subtitle">基于 Skill-Vetter 协议 · 静态分析 · 不执行技能代码</div>
    </div>
    <div class="report-meta">
        <div class="scan-id">扫描批次: {ctx.scan_id}</div>
        <div class="generated">生成时间: {ctx.generated_at}</div>
    </div>
</header>

<!-- ═══════════ STATS ═══════════ -->
<div class="stats-grid">
    <div class="stat-card total">
        <div class="stat-value">{ctx.total}</div>
        <div class="stat-label">📦 扫描总数</div>
    </div>
    <div class="stat-card passed">
        <div class="stat-value">{len(ctx.passed)}</div>
        <div class="stat-label">✅ 通过</div>
    </div>
    <div class="stat-card conditional">
        <div class="stat-value">{len(ctx.conditional)}</div>
        <div class="stat-label">⚠️ 有条件通过</div>
    </div>
    <div class="stat-card rejected">
        <div class="stat-value">{len(ctx.rejected)}</div>
        <div class="stat-label">🚫 淘汰</div>
    </div>
    <div class="stat-card avg-score">
        <div class="stat-value">{_calc_avg_score(ctx.results)}</div>
        <div class="stat-label">⭐ 平均综合评分</div>
    </div>
</div>

<!-- ═══════════ 五维度平均评分 ═══════════ -->
<div class="section">
    <h2><span class="emoji">📊</span> 五维度审计评分总览（5 分制）</h2>
    <div class="dimension-grid">
        {_render_dim_cards(ctx)}
    </div>
</div>

<!-- ═══════════ 风险分布 ═══════════ -->
<div class="section">
    <h2><span class="emoji">🎯</span> 风险等级分布</h2>
    {_render_risk_bar(ctx)}
</div>

<!-- ═══════════ 分类统计 ═══════════ -->
<div class="section">
    <h2><span class="emoji">📂</span> 分类统计</h2>
    <div class="table-wrap">
        <table>
            <thead><tr>
                <th>分类</th><th>总数</th><th>✅ 通过</th><th>⚠️ 有条件</th><th>🚫 淘汰</th><th>通过率</th>
            </tr></thead>
            <tbody>
                {_render_category_rows(ctx)}
            </tbody>
        </table>
    </div>
</div>

<!-- ═══════════ 通过技能清单 ═══════════ -->
{_render_skill_list_section(ctx)}

<!-- ═══════════ 淘汰/有条件清单 ═══════════ -->
{_render_rejected_section(ctx)}

<!-- ═══════════ 红牌命中详情 ═══════════ -->
{_render_red_flag_section(ctx)}

<!-- ═══════════ FOOTER ═══════════ -->
<footer class="report-footer">
    <p>SkillScan v1.0 · 基于 Skill-Vetter 安全审查协议</p>
    <p>纯静态分析 · 不执行任何技能代码 · 企业内网安全审计工具</p>
</footer>
</div>

<script>
// Simple collapsible toggle
document.querySelectorAll('.collapsible-toggle').forEach(toggle => {{
    toggle.addEventListener('click', () => {{
        const target = document.getElementById(toggle.dataset.target);
        if (target) {{
            const isHidden = target.style.display === 'none';
            target.style.display = isHidden ? 'block' : 'none';
            toggle.querySelector('.toggle-icon').textContent = isHidden ? '▼' : '▶';
        }}
    }});
}});
</script>
</body>
</html>"""


# ─── Template helper functions ────────────────────────

def _calc_avg_score(results) -> str:
    if not results:
        return "0.0"
    avg = sum(r.total_score for r in results) / len(results)
    return f"{avg:.1f}"


def _render_dim_cards(ctx: ReportContext) -> str:
    cards = []
    dim_order = ["source_trust", "network_isolation", "permission_minimality",
                 "code_security", "offline_compat"]
    for dim_key in dim_order:
        avg = ctx.dimension_averages.get(dim_key, 0)
        display = DIMENSION_DISPLAY.get(dim_key, dim_key)
        icon = DIMENSION_ICONS.get(dim_key, "")
        color = _score_color(avg)
        width = (avg / 5) * 100
        cards.append(f"""
        <div class="dim-card">
            <div class="dim-icon">{icon}</div>
            <div class="dim-name">{display}</div>
            <div class="dim-score" style="color:{color}">{avg:.1f}</div>
            <div class="dim-max">/ 5 分</div>
            <div class="dim-bar-bg">
                <div class="dim-bar-fill" style="width:{width}%;background:{color}"></div>
            </div>
        </div>""")
    return "\n".join(cards)


def _render_risk_bar(ctx: ReportContext) -> str:
    dist = ctx.risk_distribution
    total = ctx.total or 1

    segments = [
        ("LOW", "#22c55e", "🟢 低风险"),
        ("MEDIUM", "#eab308", "🟡 中风险"),
        ("HIGH", "#ef4444", "🔴 高风险"),
        ("EXTREME", "#7c3aed", "⛔ 极高风险"),
    ]

    bar_parts = []
    legend_parts = []
    for level, color, label in segments:
        count = dist.get(level, 0)
        pct = (count / total) * 100
        if count > 0:
            bar_parts.append(
                f'<div class="risk-bar-segment" style="flex:{count};background:{color}" title="{label}: {count} 个">{pct:.0f}%</div>'
            )
        legend_parts.append(
            f'<span><span class="risk-dot" style="background:{color}"></span> {label}: {count} 个</span>'
        )

    if not bar_parts:
        bar_parts = ['<div class="risk-bar-segment" style="flex:1;background:#334155">—</div>']

    return f"""
    <div class="risk-bar-container">{''.join(bar_parts)}</div>
    <div class="risk-legend">{''.join(legend_parts)}</div>"""


def _render_category_rows(ctx: ReportContext) -> str:
    rows = []
    for cat in ctx.category_stats:
        total = cat["total"]
        pct = (cat["passed"] / total * 100) if total > 0 else 0
        rows.append(f"""
        <tr>
            <td><span class="cat-chip">{cat['category']}</span></td>
            <td>{total}</td>
            <td style="color:var(--green)">{cat['passed']}</td>
            <td style="color:var(--yellow)">{cat['conditional']}</td>
            <td style="color:var(--red)">{cat['rejected']}</td>
            <td>{pct:.0f}%</td>
        </tr>""")
    return "\n".join(rows)


def _render_skill_list_section(ctx: ReportContext) -> str:
    """通过技能清单（按分类和风险分组）"""
    by_category: dict[str, list] = {}
    for r in ctx.passed:
        cat = r.category or "其他"
        by_category.setdefault(cat, []).append(r)
    for r in ctx.conditional:
        cat = r.category or "其他"
        by_category.setdefault(cat, []).append(r)

    if not by_category:
        return ""

    sections = []
    for cat, skills in sorted(by_category.items()):
        skills_sorted = sorted(skills, key=lambda s: s.total_score, reverse=True)
        rows = []
        for i, s in enumerate(skills_sorted, 1):
            risk_badge = _risk_badge(s.risk_level.value)
            verdict_badge = _verdict_badge(s.verdict.value)
            red_flag_info = ""
            if s.red_flag_hits:
                rule_ids = ", ".join(sorted(set(h.rule_id for h in s.red_flag_hits)))
                red_flag_info = f'<br><span style="color:var(--red);font-size:11px">🚨 {rule_ids}</span>'
            rows.append(f"""
            <tr>
                <td>{i}</td>
                <td class="slug-col">{s.slug}</td>
                <td class="name-col">{s.name or s.slug}</td>
                <td class="purpose-col">{s.description_zh or '—'}</td>
                <td>{risk_badge}</td>
                <td class="score-col">{s.total_score:.1f}</td>
                <td>{verdict_badge}</td>
            </tr>""")

        sections.append(f"""
        <div class="section">
            <h2><span class="emoji">📋</span> {cat} ({len(skills_sorted)} 个)</h2>
            <div class="table-wrap">
                <table>
                    <thead><tr>
                        <th>#</th><th>Slug</th><th>名称</th><th>用途</th><th>风险</th><th>评分</th><th>结论</th>
                    </tr></thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            </div>
        </div>""")

    return "".join(sections)


def _render_rejected_section(ctx: ReportContext) -> str:
    """淘汰和条件通过技能清单"""
    parts = []

    # 淘汰技能
    if ctx.rejected:
        rows = []
        for i, s in enumerate(ctx.rejected, 1):
            rule_ids = ", ".join(sorted(set(h.rule_id for h in s.red_flag_hits)))
            rows.append(f"""
            <tr>
                <td>{i}</td>
                <td class="slug-col">{s.slug}</td>
                <td class="name-col">{s.name or s.slug}</td>
                <td class="purpose-col">{s.description_zh or '—'}</td>
                <td><span class="badge badge-reject">淘汰</span></td>
                <td>{s.total_score:.1f}</td>
                <td style="color:var(--red);font-size:12px">{rule_ids or s.summary[:60]}</td>
            </tr>""")

        parts.append(f"""
        <div class="section">
            <h2><span class="emoji">🚫</span> 淘汰技能清单 ({len(ctx.rejected)} 个)</h2>
            <div class="table-wrap">
                <table>
                    <thead><tr>
                        <th>#</th><th>Slug</th><th>名称</th><th>用途</th><th>结论</th><th>评分</th><th>淘汰原因</th>
                    </tr></thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            </div>
        </div>""")

    return "".join(parts)


def _render_red_flag_section(ctx: ReportContext) -> str:
    """红牌命中汇总"""
    all_hits = []
    for r in ctx.results:
        for hit in r.red_flag_hits:
            all_hits.append((r.slug, r.name, hit))

    if not all_hits:
        return ""

    items = []
    for slug, name, hit in all_hits:
        items.append(f"""
        <div class="flag-item">
            <div class="flag-rule">
                <span class="badge badge-rule">{hit.rule_id}</span> {hit.rule_name}
                — <span style="color:var(--text-secondary)">{name or slug}</span>
            </div>
            <div class="flag-file">📄 {hit.file_path}</div>
            <div class="flag-content">{_escape_html(hit.matched_content[:300])}</div>
        </div>""")

    return f"""
    <div class="section">
        <h2><span class="emoji">🚨</span> 红牌规则命中详情 ({len(all_hits)} 条)</h2>
        <div class="collapsible-toggle" data-target="red-flag-details">
            <span class="toggle-icon">▼</span> 展开/收起详情
        </div>
        <div class="collapsible-content" id="red-flag-details">
            {''.join(items)}
        </div>
    </div>"""


def _risk_badge(level: str) -> str:
    cls = {"LOW": "badge-low", "MEDIUM": "badge-medium",
           "HIGH": "badge-high", "EXTREME": "badge-extreme"}
    texts = {"LOW": "🟢 低", "MEDIUM": "🟡 中", "HIGH": "🔴 高", "EXTREME": "⛔ 极高"}
    return f'<span class="badge {cls.get(level, "")}">{texts.get(level, level)}</span>'


def _verdict_badge(verdict: str) -> str:
    if "通过" == verdict:
        return '<span class="badge badge-pass">✅ 通过</span>'
    elif "有条件" in verdict:
        return '<span class="badge badge-conditional">⚠️ 有条件</span>'
    else:
        return '<span class="badge badge-reject">🚫 淘汰</span>'


def _score_color(score: float) -> str:
    if score >= 4.0: return "#22c55e"
    elif score >= 3.0: return "#eab308"
    elif score >= 2.0: return "#f97316"
    else: return "#ef4444"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
