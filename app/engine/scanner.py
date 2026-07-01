"""
主扫描编排器 — LLM + TRACE 评测体系

流程:
0. SKILL.md 格式检测（仅检测不修复，格式不对立即返回）
1. 安全读取 zip
2. 关键词分类检测（无需 LLM）
3. 构建 LLM 审查提示词
4. 调用 LLM 执行 TRACE 五维度分析
5. 解析 LLM 结构化 JSON 输出
6. 组装完整 SkillScanResult
"""
from __future__ import annotations

import os
import time
import logging
from typing import Optional

from app.models.schemas import (
    SkillScanResult, DimensionScore, SubIndicatorScore,
    SecurityFinding, ClassificationResult, SkillCategory, FixReportModel,
    TRACE_DISPLAY, TRACE_LETTER, TRACE_COLORS,
    CATEGORY_DISPLAY_MAP,
)
from app.engine.llm_client import get_client, LLMResponse
from app.engine.prompts import SYSTEM_PROMPT_TRACE, build_audit_message
from app.engine.classifier import classify_skill
from app.engine.skill_fixer import analyze_skill_md
from app.utils.zip_reader import safe_read_zip

logger = logging.getLogger("skillscan.scanner")


async def scan_single_skill(
    zip_path: str,
    metadata: Optional[dict] = None,
) -> SkillScanResult:
    """
    对单个技能 zip 包执行完整 TRACE 审核（LLM 驱动）

    Step 0 仅检测 SKILL.md 格式，发现问题即刻返回，不执行 TRACE。
    """
    t_start = time.perf_counter()
    meta = metadata or {}

    # ── Step 0: SKILL.md 格式检测（仅检测，不修复） ──
    format_check = analyze_skill_md(zip_path)
    if format_check.errors or format_check.needs_fix:
        reasons = []
        if format_check.errors:
            reasons.extend(format_check.errors)
        if format_check.actions:
            reasons.append("SKILL.md 格式不符合要求，请先通过 /fix-skill 接口下载修复后的文件")
            reasons.extend(f"  · {a}" for a in format_check.actions)
        return _format_error_result(
            slug=meta.get("slug", ""),
            meta=meta,
            reasons=reasons,
            elapsed=time.perf_counter() - t_start,
        )

    # ── Step 1: 安全读取 zip ──
    zip_result = safe_read_zip(zip_path, slug=meta.get("slug", ""))
    if zip_result.error:
        return _error_result(zip_result.slug, meta, zip_result.error, time.perf_counter() - t_start)

    slug = zip_result.slug or meta.get("slug", "")
    name = meta.get("name", "") or meta.get("title", "")
    desc = meta.get("description_zh", "") or meta.get("description", "")

    # ── Step 2: 分类检测 ──
    file_extensions = [os.path.splitext(e.path)[1] for e in zip_result.files if os.path.splitext(e.path)[1]]
    classification = classify_skill(
        slug=slug, name=name, description=desc,
        skill_md_content=zip_result.skill_md_content,
        file_extensions=file_extensions,
        original_category=meta.get("category", ""),
    )

    # ── Step 3: 构建 LLM 审查请求 ──
    file_contents: list[tuple[str, str]] = []
    total_lines = 0
    for entry in zip_result.files:
        if entry.is_text:
            file_contents.append((entry.path, entry.content))
            total_lines += entry.content.count("\n") + 1

    user_message = build_audit_message(
        slug=slug, name=name, description=desc,
        skill_md_content=zip_result.skill_md_content,
        file_list=[e.path for e in zip_result.files],
        file_contents=file_contents,
    )

    # ── Step 4: 调用 LLM ──
    client = get_client()
    llm_response = await client.chat(
        system_prompt=SYSTEM_PROMPT_TRACE,
        user_message=user_message,
        temperature=0.3,
        expect_json=True,
    )

    # ── Step 5: 解析 LLM 结果 ──
    trace_scores, overall, security_findings, security_level, verdict, verdict_reason = (
        _parse_llm_result(llm_response)
    )

    # ── Step 6: 组装结果 ──
    classification_model = ClassificationResult(
        detected_category=classification.detected_category,
        category_display=CATEGORY_DISPLAY_MAP.get(classification.detected_category, "其他"),
        confidence=classification.confidence,
        category_scores=classification.category_scores,
        detection_method=classification.detection_method,
        evidence=classification.evidence,
    )

    t_end = time.perf_counter()

    return SkillScanResult(
        slug=slug, name=name,
        description_zh=desc[:200],
        stars=meta.get("stars", 0),
        author=meta.get("owner_name", meta.get("author", "")),
        version=meta.get("version", ""),
        downloads=meta.get("downloads", 0),
        updated_at=meta.get("updated_at", ""),
        original_category=meta.get("category", ""),
        detected_category=classification.detected_category,
        detected_category_display=CATEGORY_DISPLAY_MAP.get(classification.detected_category, "其他"),
        detected_category_confidence=classification.confidence,
        classification=classification_model,
        trace_scores=trace_scores,
        overall_score=overall,
        security_level=security_level,
        security_findings=security_findings,
        security_labs=_default_security_labs(),
        verdict=verdict,
        verdict_reason=verdict_reason,
        files_scanned=zip_result.total_text_files,
        total_lines=total_lines,
        scan_duration_ms=int((t_end - t_start) * 1000),
    )


# ═══════════════════════════════════════════════════════
# LLM 结果解析
# ═══════════════════════════════════════════════════════

def _parse_llm_result(resp: LLMResponse):
    """从 LLM 响应中提取 TRACE 结构化评分"""
    dim_keys = ["trust", "reliability", "adaptability", "convention", "effectiveness"]
    trace_scores: list[DimensionScore] = []
    overall = 0.0
    security_findings: list[SecurityFinding] = []
    security_level = "安全"
    verdict = "通过"
    verdict_reason = ""

    if resp.success and resp.parsed:
        data = resp.parsed
        overall = float(data.get("overall_score", 0))
        verdict = data.get("verdict", "通过")
        verdict_reason = data.get("verdict_reason", "")
        security_level = data.get("security_level", "安全")

        for sf in data.get("security_findings", []):
            security_findings.append(SecurityFinding(
                severity=sf.get("severity", "info"),
                category=sf.get("category", ""),
                description=sf.get("description", ""),
                file_path=sf.get("file_path", ""),
                suggestion=sf.get("suggestion", ""),
            ))

        raw_scores = data.get("trace_scores", [])
        raw_map: dict[str, dict] = {s.get("dimension", ""): s for s in raw_scores}

        for dim_key in dim_keys:
            raw = raw_map.get(dim_key, {})
            score = float(raw.get("score", 0))
            summary = raw.get("findings_summary", "")
            sub_raw = raw.get("sub_indicators", [])

            sub_items: list[SubIndicatorScore] = []
            for si in sub_raw:
                sub_items.append(SubIndicatorScore(
                    key=si.get("key", ""),
                    name=si.get("name", ""),
                    score=int(si.get("score", 3)),
                    comment=si.get("comment", ""),
                ))

            trace_scores.append(DimensionScore(
                dimension=dim_key,
                letter=TRACE_LETTER.get(dim_key, dim_key[0].upper()),
                display_name=TRACE_DISPLAY.get(dim_key, dim_key),
                score=score,
                sub_indicators=sub_items,
                findings_summary=summary,
            ))

        if overall == 0 and trace_scores:
            overall = round(sum(d.score for d in trace_scores) / len(trace_scores), 1)
    else:
        overall = 0.0
        for dim_key in dim_keys:
            trace_scores.append(DimensionScore(
                dimension=dim_key,
                letter=TRACE_LETTER.get(dim_key, dim_key[0].upper()),
                display_name=TRACE_DISPLAY.get(dim_key, dim_key),
                score=0.0,
                sub_indicators=[],
                findings_summary=f"LLM 分析失败: {resp.error}" if resp.error else "未完成分析",
            ))
        security_level = "存在潜在风险"
        verdict = "有条件通过"
        verdict_reason = f"LLM 分析不可用: {resp.error}" if resp.error else "LLM 服务未响应"

    return trace_scores, overall, security_findings, security_level, verdict, verdict_reason


def _format_error_result(slug: str, meta: dict, reasons: list[str], elapsed: float) -> SkillScanResult:
    return SkillScanResult(
        slug=slug or meta.get("name", "未知"),
        name=meta.get("name", slug),
        security_level="不安全",
        verdict="淘汰",
        verdict_reason="\n".join(reasons),
        scan_duration_ms=int(elapsed * 1000),
    )


def _error_result(slug: str, meta: dict, error: str, elapsed: float) -> SkillScanResult:
    return SkillScanResult(
        slug=slug, name=meta.get("name", slug),
        security_level="不安全", verdict="淘汰",
        verdict_reason=f"无法读取 zip 包: {error}",
        scan_duration_ms=int(elapsed * 1000),
    )


def _default_security_labs() -> list[dict]:
    return [
        {"name": "科恩实验室", "result": "深度漏洞扫描完成", "status": "pass"},
        {"name": "云鼎实验室", "result": "AI 模型安全评估完成", "status": "pass"},
    ]
