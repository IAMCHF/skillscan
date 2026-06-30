"""
主扫描编排器 — 整合 Skill-Vetter 三部分审查并生成 5 分制多维度评分

流程:
1. 安全读取 zip（不解压，仅提取文本文件）
2. Source Check（来源检查 → 可信度评分）
3. Red Flag Scan（15 条红牌规则 → 安全评分）
4. Permission Analysis（权限范围 → 权限评分）
5. Offline Compatibility（离线兼容性 → 网络隔离+离线评分）
6. 综合计算 5 维度评分 → 风险分级 → 生成 HTML 报告
"""

from __future__ import annotations

import re
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.schemas import (
    SkillScanResult, SourceCheckResult, RedFlagHit, PermissionScope,
    DimensionScore, RiskLevel, Verdict, AuditDimension, BatchScanResponse,
    ReportContext, DIMENSION_DISPLAY, DIMENSION_ICONS,
)
from app.engine.red_flags import RED_FLAG_RULES
from app.engine.source_check import check_source
from app.engine.permission import analyze_permissions
from app.utils.zip_reader import safe_read_zip, SKILL_MD_NAMES


# ─── 安全域名白名单（Phase 2 逻辑复用）─────────────────

SAFE_DOMAINS = frozenset({
    "localhost", "127.0.0.1", "192.168.",
    "github.com", "github.io", "gitlab.com", "bitbucket.org",
    "pypi.org", "npmjs.com", "crates.io",
    "skillhub.cn", "clawhub.ai", "openclaw.ai",
    "docs.python.org", "developer.mozilla.org", "readthedocs.io",
    "arxiv.org", "doi.org", "owasp.org",
    "example.com", "example.org",
    "wikipedia.org", "stackoverflow.com",
    "w3.org", "schema.org",
})

NETWORK_TOOL_KEYWORDS = [
    "web_search", "web_fetch", "browser tool", "browser use",
    "playwright", "selenium", "puppeteer", "cypress",
    "webdriver", "scrape", "crawl",
]


def scan_single_skill(zip_path: str, metadata: Optional[dict] = None) -> SkillScanResult:
    """
    对单个技能 zip 包执行完整静态安全审查

    Args:
        zip_path: 技能 zip 文件路径
        metadata: 可选的额外元数据 (slug, name, category, stars, etc.)

    Returns:
        SkillScanResult 包含完整的五维度评分、红牌命中、权限分析等
    """
    t_start = time.perf_counter()
    meta = metadata or {}

    # ── Step 1: 安全读取 zip ──
    zip_result = safe_read_zip(zip_path, slug=meta.get("slug", ""))

    if zip_result.error:
        # 无法读取的 zip 直接淘汰
        return _make_error_result(zip_result, meta)

    slug = zip_result.slug or meta.get("slug", "")
    name = meta.get("name", "") or meta.get("title", "")
    category = meta.get("category", "")
    description_zh = meta.get("description_zh", "") or meta.get("description", "")

    # ── Step 2: Source Check ──
    source_check = check_source(
        slug=slug,
        author_name=meta.get("owner_name", meta.get("author", "")),
        stars=meta.get("stars", 0),
        category=category,
        description_zh=description_zh,
        last_updated=meta.get("updated_at", ""),
    )

    # ── Step 3: Red Flag Scan ──
    red_flag_hits: list[RedFlagHit] = []

    # 3a. 检查二进制文件 (R15)
    if zip_result.has_binary_files:
        for bf in zip_result.binary_files:
            red_flag_hits.append(RedFlagHit(
                rule_id="R15", rule_name="包含二进制可执行文件",
                description="zip 包内包含二进制可执行文件",
                file_path=bf, matched_content=bf, severity="EXTREME",
            ))

    # 3b. 扫描所有文本文件内容
    all_text_contents: list[tuple[str, str]] = []
    for entry in zip_result.files:
        if not entry.is_text:
            continue
        all_text_contents.append((entry.path, entry.content))

        # 跳过 SKILL.md（单独处理）
        if entry.is_skill_md:
            continue

        for rule in RED_FLAG_RULES:
            if not rule.patterns:  # R15 已在上面处理
                continue
            for pattern in rule.patterns:
                try:
                    for match in re.finditer(pattern, entry.content, re.IGNORECASE):
                        hit_content = entry.content[
                            max(0, match.start()-20):match.end()+50
                        ]
                        red_flag_hits.append(RedFlagHit(
                            rule_id=rule.rule_id,
                            rule_name=rule.name,
                            description=rule.description,
                            file_path=entry.path,
                            matched_content=hit_content[:200],
                            severity=rule.severity,
                        ))
                except re.error:
                    continue

    # 3c. 去重红牌命中 (同文件同规则只计一次)
    seen = set()
    unique_hits: list[RedFlagHit] = []
    for hit in red_flag_hits:
        key = (hit.rule_id, hit.file_path)
        if key not in seen:
            seen.add(key)
            unique_hits.append(hit)
    red_flag_hits = unique_hits

    # ── Step 4: Permission Scope Analysis ──
    permission_scope = analyze_permissions(
        zip_result.skill_md_content,
        all_text_contents,
    )

    # ── Step 5: Five-Dimension Scoring ──

    # 5a. 来源可信度 (1-5)
    source_score = source_check.trust_score

    # 5b. 网络隔离度 (1-5)
    # 扫描所有文本内容中的 URL
    all_content = zip_result.skill_md_content
    for path, content in all_text_contents:
        all_content += "\n" + content

    urls = re.findall(r'https?://[^\s\)\]\"\']+', all_content)
    external_urls = [
        u for u in urls
        if not any(d in u.lower() for d in SAFE_DOMAINS)
    ]
    has_network_tools = any(
        kw in all_content.lower() for kw in NETWORK_TOOL_KEYWORDS
    )
    has_network_code = permission_scope.network_requirement in ("外部网络", "可能存在")

    if has_network_tools:
        network_score = 1
    elif has_network_code and external_urls:
        network_score = 2
    elif external_urls and not has_network_code:
        network_score = 3
    elif has_network_code and not external_urls:
        network_score = 3
    elif not external_urls and not has_network_code:
        # 检查是否使用了纯本地工具（无网络需求）
        network_score = 5
    else:
        network_score = 4

    # 5c. 权限最小化 (1-5)
    has_file_ops = bool(permission_scope.file_read_patterns or permission_scope.file_write_patterns)
    has_commands = bool(permission_scope.commands_detected)
    has_dangerous = permission_scope.has_dangerous_commands
    scope_matches = permission_scope.scope_matches_function

    if has_dangerous:
        perm_score = 1
    elif has_commands and has_file_ops and not scope_matches:
        perm_score = 2
    elif has_commands and has_file_ops:
        perm_score = 3
    elif has_file_ops and not has_commands:
        perm_score = 4
    else:
        perm_score = 5

    # 5d. 代码安全性 (1-5)
    if red_flag_hits:
        security_score = 1
    else:
        # 检查有没有潜在危险的模式但不是红牌
        suspicious = _count_suspicious_patterns(all_content)
        if suspicious > 5:
            security_score = 2
        elif suspicious > 2:
            security_score = 3
        elif suspicious > 0:
            security_score = 4
        else:
            security_score = 5

    # 5e. 离线兼容性 (1-5)
    if has_network_tools:
        offline_score = 1
    elif has_network_code and external_urls:
        offline_score = 2
    elif external_urls and not has_network_code:
        offline_score = 3
    elif not zip_result.has_binary_files and not has_network_code:
        offline_score = 5
    else:
        offline_score = 4

    # ── Step 6: 综合风险判定 ──

    # 命中红牌 → EXTREME
    if red_flag_hits:
        risk_level = RiskLevel.EXTREME
        verdict = Verdict.REJECT
    elif perm_score <= 2 or security_score <= 2:
        risk_level = RiskLevel.HIGH
        verdict = Verdict.CONDITIONAL
    elif network_score <= 2 or offline_score <= 2:
        risk_level = RiskLevel.MEDIUM
        verdict = Verdict.CONDITIONAL
    elif perm_score <= 3:
        risk_level = RiskLevel.MEDIUM
        verdict = Verdict.PASS
    else:
        risk_level = RiskLevel.LOW
        verdict = Verdict.PASS

    # ── Step 7: 组装 DimensionScores ──
    dimension_scores = [
        _make_dimension("source_trust", source_score, [
            f"作者可信度: {source_check.author_trust_level}/5",
            f"星标: {source_check.stars}",
            f"分类匹配: {'是' if source_check.category_match else '否'}",
        ]),
        _make_dimension("network_isolation", network_score, [
            f"外部 URL: {len(external_urls)} 个",
            f"网络工具关键词: {'发现' if has_network_tools else '未发现'}",
            f"网络依赖: {permission_scope.network_requirement}",
        ]),
        _make_dimension("permission_minimality", perm_score, [
            f"文件读取: {len(permission_scope.file_read_patterns)} 类操作",
            f"文件写入: {len(permission_scope.file_write_patterns)} 类操作",
            f"命令执行: {len(permission_scope.commands_detected)} 类操作",
            f"危险命令: {'发现' if has_dangerous else '未发现'}",
        ]),
        _make_dimension("code_security", security_score, [
            f"红牌命中: {len(red_flag_hits)} 条",
            f"可疑模式: {_count_suspicious_patterns(all_content)} 处",
        ]),
        _make_dimension("offline_compat", offline_score, [
            f"网络工具: {'检测到' if has_network_tools else '未检测到'}",
            f"二进制文件: {len(zip_result.binary_files)} 个",
            f"外部 URL: {len(external_urls)} 个",
        ]),
    ]

    total_score = sum(d.score for d in dimension_scores) / 5.0

    # 生成摘要
    summary = _generate_summary(
        slug, name, risk_level, verdict,
        red_flag_hits, dimension_scores, total_score,
    )

    t_end = time.perf_counter()
    scan_duration_ms = int((t_end - t_start) * 1000)

    return SkillScanResult(
        slug=slug,
        name=name,
        category=category,
        description_zh=description_zh[:80],
        stars=meta.get("stars", 0),
        source_check=source_check,
        red_flag_hits=red_flag_hits,
        permission_scope=permission_scope,
        dimension_scores=dimension_scores,
        total_score=round(total_score, 1),
        risk_level=risk_level,
        verdict=verdict,
        files_scanned=zip_result.total_text_files,
        scan_duration_ms=scan_duration_ms,
        summary=summary,
    )


def build_report_context(scan_id: str, results: list[SkillScanResult]) -> ReportContext:
    """构建 HTML 报告所需的完整上下文数据"""
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    # 风险分布
    risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "EXTREME": 0}
    for r in results:
        risk_dist[r.risk_level.value] = risk_dist.get(r.risk_level.value, 0) + 1

    # 维度平均分
    dim_totals: dict[str, list[int]] = {}
    for r in results:
        for ds in r.dimension_scores:
            dim_totals.setdefault(ds.dimension, []).append(ds.score)
    dimension_averages = {
        dim: round(sum(scores) / len(scores), 1)
        for dim, scores in dim_totals.items()
    }

    # 红牌汇总
    red_flag_summary: dict[str, int] = {}
    for r in results:
        for hit in r.red_flag_hits:
            key = f"{hit.rule_id}: {hit.rule_name}"
            red_flag_summary[key] = red_flag_summary.get(key, 0) + 1

    # 分类统计
    cat_stats: dict[str, dict] = {}
    for r in results:
        cat = r.category or "其他"
        if cat not in cat_stats:
            cat_stats[cat] = {"category": cat, "total": 0, "passed": 0,
                              "conditional": 0, "rejected": 0}
        cat_stats[cat]["total"] += 1
        if r.verdict == Verdict.PASS:
            cat_stats[cat]["passed"] += 1
        elif r.verdict == Verdict.CONDITIONAL:
            cat_stats[cat]["conditional"] += 1
        else:
            cat_stats[cat]["rejected"] += 1

    passed = [r for r in results if r.verdict == Verdict.PASS]
    conditional = [r for r in results if r.verdict == Verdict.CONDITIONAL]
    rejected = [r for r in results if r.verdict == Verdict.REJECT]

    return ReportContext(
        scan_id=scan_id,
        generated_at=now,
        total=len(results),
        results=results,
        risk_distribution=risk_dist,
        dimension_averages=dimension_averages,
        red_flag_summary=red_flag_summary,
        category_stats=list(cat_stats.values()),
        rejected=rejected,
        conditional=conditional,
        passed=passed,
    )


# ─── Private Helpers ──────────────────────────────────

_SUSPICIOUS_PATTERNS = [
    r'\.encode\s*\(\s*[\'"]base64[\'"]',
    r'pickle\.(?:loads|load)\s*\(',
    r'marshal\.loads?\s*\(',
    r'yaml\.load\s*\(',
    r'\.decode\s*\(\s*[\'"]rot13[\'"]',
    r'socket\.socket\s*\(',
    r'ctypes\.(?:CDLL|WinDLL)\s*\(',
    r'\._?private',
]


def _count_suspicious_patterns(content: str) -> int:
    count = 0
    for pattern in _SUSPICIOUS_PATTERNS:
        count += len(re.findall(pattern, content, re.IGNORECASE))
    return count


def _make_dimension(dim: str, score: int, findings: list[str]) -> DimensionScore:
    return DimensionScore(
        dimension=dim,
        score=score,
        max_score=5,
        display_name=DIMENSION_DISPLAY.get(dim, dim),
        icon=DIMENSION_ICONS.get(dim, ""),
        reason=f"评分 {score}/5",
        findings=findings,
    )


def _generate_summary(
    slug: str, name: str, risk_level: RiskLevel, verdict: Verdict,
    red_flag_hits: list[RedFlagHit], dimension_scores: list[DimensionScore],
    total_score: float,
) -> str:
    level_display = RiskLevel.display(risk_level.value)
    verdict_display = verdict.value

    parts = [
        f"技能 [{name or slug}] 综合评分 {total_score}/5",
        f"风险等级: {level_display}",
        f"审查结论: {verdict_display}",
    ]

    if red_flag_hits:
        rule_list = ", ".join(
            sorted(set(h.rule_id for h in red_flag_hits))
        )
        parts.append(f"命中红牌: {rule_list}")

    # 最低分维度
    min_dim = min(dimension_scores, key=lambda d: d.score)
    parts.append(f"最低维度: {min_dim.display_name} ({min_dim.score}/5)")

    return "。".join(parts)


def _make_error_result(zip_result, meta: dict) -> SkillScanResult:
    return SkillScanResult(
        slug=zip_result.slug,
        name=meta.get("name", zip_result.slug),
        risk_level=RiskLevel.EXTREME,
        verdict=Verdict.REJECT,
        summary=f"无法读取: {zip_result.error}",
        total_score=0,
    )
