"""
技能分类检测引擎 — LLM 驱动分类，关键词加权作为降级备用
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging

from app.engine.llm_client import get_client
from app.engine.prompts import SYSTEM_PROMPT_CLASSIFY

logger = logging.getLogger("skillscan.classifier")

CATEGORY_DISPLAY: dict[str, str] = {
    "aiAgent": "AI 智能", "itOpsSecurity": "IT 运维/安全",
    "development": "开发工具", "dataAnalysis": "数据分析",
    "contentCreation": "内容创作", "officeEfficiency": "办公效率",
    "others": "其他",
}

ALL_CATEGORIES = list(CATEGORY_DISPLAY.keys())


@dataclass
class ClassificationResult:
    detected_category: str = "others"
    confidence: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    detection_method: str = "default"
    evidence: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════
# LLM 分类（主路径）
# ═══════════════════════════════════════════════════════

async def classify_skill(
    skill_md_content: str,
    slug: str = "",
    name: str = "",
    description: str = "",
    original_category: str = "",
    file_extensions: list[str] | None = None,
) -> ClassificationResult:
    """
    使用 LLM 对技能进行分类。

    根据 SKILL.md 内容调用 LLM 进行语义分类。
    LLM 失败时降级为关键词分类。
    """
    user_message = _build_classify_message(skill_md_content, slug, name, description, original_category)

    client = get_client()
    llm_resp = await client.chat(
        system_prompt=SYSTEM_PROMPT_CLASSIFY,
        user_message=user_message,
        temperature=0.1,
        expect_json=True,
    )

    if llm_resp.success and llm_resp.parsed:
        result = _parse_classify_result(llm_resp.parsed)
        logger.info(f"LLM 分类成功: slug={slug}, category={result.detected_category}, confidence={result.confidence}")
        return result

    # LLM 失败，降级到关键词分类
    logger.warning(f"LLM 分类失败，降级为关键词分类: slug={slug}, error={llm_resp.error}")
    return _classify_keywords(
        slug=slug, name=name, description=description,
        skill_md_content=skill_md_content,
        file_extensions=file_extensions,
        original_category=original_category,
    )


def _build_classify_message(
    skill_md_content: str,
    slug: str,
    name: str,
    description: str,
    original_category: str,
) -> str:
    """构建 LLM 分类请求的用户消息"""
    parts = [
        "请对以下 AI 技能进行分类。",
        "",
        f"## 技能元数据",
        f"- Slug: {slug}",
        f"- 名称: {name}",
        f"- 描述: {description}",
        f"- 原始分类: {original_category}",
    ]

    if skill_md_content:
        truncated = skill_md_content[:6000]
        if len(skill_md_content) > 6000:
            truncated += "\n\n... [内容过长，已截断]"
        parts.append(f"\n## SKILL.md 内容\n{truncated}")

    return "\n".join(parts)


def _parse_classify_result(data: dict) -> ClassificationResult:
    """解析 LLM 返回的分类 JSON"""
    detected = data.get("detected_category", "others")
    if detected not in CATEGORY_DISPLAY:
        detected = "others"

    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    raw_scores = data.get("category_scores", {})
    category_scores = {}
    for cat in ALL_CATEGORIES:
        score = float(raw_scores.get(cat, 0.0))
        category_scores[cat] = max(0.0, min(1.0, round(score, 2)))

    evidence = data.get("evidence", [])
    if not evidence:
        evidence = [f"LLM 分类判定为: {CATEGORY_DISPLAY.get(detected, '其他')}"]

    return ClassificationResult(
        detected_category=detected,
        confidence=confidence,
        category_scores=category_scores,
        detection_method="LLM语义分类",
        evidence=evidence,
    )


# ═══════════════════════════════════════════════════════
# 关键词分类（降级备用）
# ═══════════════════════════════════════════════════════

SLUG_KEYWORDS: dict[str, list[str]] = {
    "aiAgent": ["agent", "ai-agent", "agentic", "autonomy", "memory", "orchestrat", "swarm", "agent-team", "llm", "gpt", "claude", "rag", "prompt-engin", "agent-factory", "neural-memory"],
    "itOpsSecurity": ["security", "vulnerab", "firewall", "cyber", "threat", "audit", "compliance", "siem", "ops", "devops", "k8s", "kubernetes", "docker", "deploy", "monitor", "terraform", "ansible", "osint"],
    "development": ["code", "coding", "program", "develop", "python", "javascript", "typescript", "java", "golang", "rust", "react", "vue", "api", "database", "sql", "git", "testing", "framework", "cli", "code-review", "refactor", "sdk"],
    "dataAnalysis": ["data-analy", "analytics", "statistic", "machine-learning", "visualization", "chart", "dashboard", "etl", "pipeline", "excel", "csv", "report", "predict", "forecast", "bioinformatic", "spreadsheet"],
    "contentCreation": ["content", "creat", "writer", "writing", "blog", "article", "novel", "document", "ppt", "presentation", "slide", "design", "graphic", "image", "video", "seo", "copywriting", "social-media", "translate", "logo"],
    "officeEfficiency": ["productivity", "workflow", "automat", "efficiency", "task", "todo", "calendar", "planner", "office", "word", "wps", "email", "note", "meeting", "knowledge", "project-manag", "prd", "format", "convert", "organiz", "file-manag"],
}


def _classify_keywords(
    slug: str = "",
    name: str = "",
    description: str = "",
    skill_md_content: str = "",
    file_extensions: list[str] | None = None,
    original_category: str = "",
) -> ClassificationResult:
    """
    基于多维度加权关键词评分分类（LLM 不可用时的降级方案）
    """
    scores = {cat: 0.0 for cat in CATEGORY_DISPLAY}
    evidence = []
    slug_text = f"{slug} {name}".lower()
    desc_text = description.lower()
    full_text = f"{desc_text}\n{skill_md_content}".lower()

    for cat, keywords in SLUG_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in slug_text)
        if hits > 0:
            scores[cat] += min(hits * 0.6, 3.0)
            if hits >= 2:
                evidence.append(f"Slug 命中 {cat} 关键词 ({hits} 个)")

    for cat, keywords in SLUG_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in full_text)
        if hits > 2:
            scores[cat] += min(hits * 0.2, 1.5)
            evidence.append(f"全文命中 {cat} 关键词 ({hits} 个)")

    if file_extensions:
        py_count = sum(1 for e in file_extensions for x in [e.lower()] if x in (".py", "py"))
        if py_count >= 3:
            scores["development"] += 0.5
            scores["dataAnalysis"] += 0.3

    if original_category:
        mapping = {
            "aiintelligence": "aiAgent", "securitycompliance": "itOpsSecurity",
            "devtools": "development", "dataanalysis": "dataAnalysis",
            "contentcreation": "contentCreation", "productivity": "officeEfficiency",
            "communication": "officeEfficiency",
        }
        mapped = mapping.get(original_category.lower().replace("-", "").replace("_", ""), "")
        if mapped in scores:
            scores[mapped] += 0.3

    max_cat = max(scores, key=scores.get)
    max_score = scores[max_cat]
    sorted_v = sorted(scores.values(), reverse=True)
    confidence = min(
        max_score / 3.0 + (sorted_v[0] - sorted_v[1]) * 0.1
        if len(sorted_v) >= 2 and sorted_v[0] > 0 else 0.0,
        1.0,
    )
    if max_score < 0.8:
        max_cat = "others"
        confidence = 0.6

    return ClassificationResult(
        detected_category=max_cat,
        confidence=round(confidence, 2),
        category_scores={k: round(v, 2) for k, v in scores.items()},
        detection_method="多维度关键词分析（LLM 降级）" if evidence else "default",
        evidence=evidence or ["无明确分类信号"],
    )
