"""
Pydantic 数据模型 — SkillScan TRACE 评测体系

TRACE 五维度:
  T - Trust（可信任度）: 安全检测、最小权限、敏感信息保护、国内可用性、中文支持
  R - Reliability（可靠性）: 稳定运行、一致结果、边界输入处理、异常反馈机制
  A - Adaptability（适用性）: 场景匹配度、触发条件清晰度、能力边界界定、输入输出规范性
  C - Convention（规范性）: 渐进式披露、文档结构清晰度、限制说明完整性、示例充分性
  E - Effectiveness（有效性）: 结果正确性、输出完整性、可直接使用性、减少返工率

每个维度 4 个子指标，每项 0-5 分。LLM 进行语义级别分析。
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════
# TRACE 评分维度配置
# ═══════════════════════════════════════════════════════

class TraceDimension(str, Enum):
    TRUST = "trust"
    RELIABILITY = "reliability"
    ADAPTABILITY = "adaptability"
    CONVENTION = "convention"
    EFFECTIVENESS = "effectiveness"


TRACE_DISPLAY: dict[str, str] = {
    "trust": "可信任度",
    "reliability": "可靠性",
    "adaptability": "适用性",
    "convention": "规范性",
    "effectiveness": "有效性",
}

TRACE_LETTER: dict[str, str] = {
    "trust": "T", "reliability": "R", "adaptability": "A",
    "convention": "C", "effectiveness": "E",
}

TRACE_COLORS: dict[str, str] = {
    "trust": "#3b82f6", "reliability": "#10b981",
    "adaptability": "#f59e0b", "convention": "#8b5cf6",
    "effectiveness": "#ef4444",
}

# 每个维度的 4 个子指标
TRACE_SUB_INDICATORS: dict[str, list[dict[str, str]]] = {
    "trust": [
        {"key": "security", "name": "安全检测", "desc": "是否通过安全审查，有无漏洞"},
        {"key": "minimal_permission", "name": "最小权限", "desc": "是否遵循最小权限原则"},
        {"key": "sensitive_data", "name": "敏感信息保护", "desc": "是否妥善保护用户敏感数据"},
        {"key": "availability", "name": "国内可用性", "desc": "是否在国内网络环境可用"},
    ],
    "reliability": [
        {"key": "stability", "name": "稳定运行", "desc": "是否能在正常条件下稳定运行"},
        {"key": "consistency", "name": "一致结果", "desc": "相同输入是否产生一致输出"},
        {"key": "edge_cases", "name": "边界输入处理", "desc": "对边界/异常输入的容错能力"},
        {"key": "error_feedback", "name": "异常反馈机制", "desc": "遇到错误时是否有清晰的反馈"},
    ],
    "adaptability": [
        {"key": "scene_match", "name": "场景匹配度", "desc": "功能与目标场景的匹配程度"},
        {"key": "trigger_clarity", "name": "触发条件清晰度", "desc": "触发使用条件的明确性"},
        {"key": "capability_boundary", "name": "能力边界界定", "desc": "是否清晰界定能做/不能做什么"},
        {"key": "io_standard", "name": "输入输出规范性", "desc": "输入输出格式是否规范"},
    ],
    "convention": [
        {"key": "progressive_disclosure", "name": "渐进式披露", "desc": "文档是否循序渐进披露信息"},
        {"key": "doc_structure", "name": "文档结构清晰度", "desc": "SKILL.md 组织结构是否清晰"},
        {"key": "limitation_completeness", "name": "限制说明完整性", "desc": "是否完整说明能力和限制"},
        {"key": "example_sufficiency", "name": "示例充分性", "desc": "是否提供充分的典型示例"},
    ],
    "effectiveness": [
        {"key": "correctness", "name": "结果正确性", "desc": "输出结果是否正确"},
        {"key": "completeness", "name": "输出完整性", "desc": "输出是否完整无缺失"},
        {"key": "direct_usability", "name": "可直接使用性", "desc": "输出是否可直接使用"},
        {"key": "rework_reduction", "name": "减少返工率", "desc": "是否能减少后续返工"},
    ],
}


# ═══════════════════════════════════════════════════════
# 技能分类
# ═══════════════════════════════════════════════════════

class SkillCategory(str, Enum):
    AI_AGENT = "aiAgent"
    IT_OPS_SECURITY = "itOpsSecurity"
    DEVELOPMENT = "development"
    DATA_ANALYSIS = "dataAnalysis"
    CONTENT_CREATION = "contentCreation"
    OFFICE_EFFICIENCY = "officeEfficiency"
    OTHERS = "others"

    @classmethod
    def display(cls, value: str) -> str:
        return {
            "aiAgent": "AI 智能", "itOpsSecurity": "IT 运维/安全",
            "development": "开发工具", "dataAnalysis": "数据分析",
            "contentCreation": "内容创作", "officeEfficiency": "办公效率",
            "others": "其他",
        }.get(value, value)


CATEGORY_DISPLAY_MAP = {c.value: SkillCategory.display(c.value) for c in SkillCategory}

# ═══════════════════════════════════════════════════════
# 审核结论
# ═══════════════════════════════════════════════════════

class SecurityLevel(str, Enum):
    SAFE = "安全"
    POTENTIAL_RISK = "存在潜在风险"
    UNSAFE = "不安全"


class Verdict(str, Enum):
    PASS = "通过"
    CONDITIONAL = "有条件通过"
    REJECT = "淘汰"


# ═══════════════════════════════════════════════════════
# TRACE 审核结果数据模型
# ═══════════════════════════════════════════════════════

class SubIndicatorScore(BaseModel):
    """单个子指标评分"""
    key: str
    name: str          # 中文名称
    score: int = Field(ge=0, le=5, default=3)
    comment: str = ""  # LLM 评价理由


class DimensionScore(BaseModel):
    """单个 TRACE 维度的完整评分"""
    dimension: str            # trust / reliability / adaptability / convention / effectiveness
    letter: str               # T / R / A / C / E
    display_name: str         # 可信任度 / 可靠性 ...
    score: float = Field(ge=0.0, le=5.0, default=3.0)  # 维度平均分
    sub_indicators: list[SubIndicatorScore] = Field(default_factory=list)
    findings_summary: str = ""  # LLM 分析摘要


class SecurityFinding(BaseModel):
    """安全审查发现"""
    severity: str = "info"       # info / warning / critical
    category: str = ""           # 供应链风险 / 命令执行 / 网络请求 / 文件操作 / Prompt注入
    description: str = ""
    file_path: str = ""
    suggestion: str = ""


class ClassificationResult(BaseModel):
    """分类检测结果"""
    detected_category: str = "others"
    category_display: str = "其他"
    confidence: float = 0.0
    category_scores: dict[str, float] = Field(default_factory=dict)
    detection_method: str = "default"
    evidence: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════
# 格式修复报告（必须在 SkillScanResult 之前定义）
# ═══════════════════════════════════════════════════════

class FixReportModel(BaseModel):
    """SKILL.md 格式检测与自动修复报告"""
    zip_fixed: bool = False                     # 是否执行了修复
    actions: list[str] = Field(default_factory=list)   # 修复动作描述
    errors: list[str] = Field(default_factory=list)    # 修复错误
    extracted_name: str = ""                    # 从修复中提取的 name
    extracted_desc: str = ""                    # 从修复中提取的 description


class SkillScanResult(BaseModel):
    """单个技能的完整 TRACE 审核结果 — 与 HTML 模板字段一一对应"""
    # ── 基础信息 ──
    slug: str
    name: str = ""
    description_zh: str = ""
    stars: int = 0
    author: str = ""
    version: str = ""
    downloads: int = 0
    updated_at: str = ""

    # ── 分类 ──
    original_category: str = ""
    detected_category: str = "others"
    detected_category_display: str = "其他"
    detected_category_confidence: float = 0.0
    classification: ClassificationResult = Field(default_factory=ClassificationResult)

    # ── TRACE 五维度评分 ──
    trace_scores: list[DimensionScore] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0.0, le=5.0)  # AI 综合评分

    # ── 安全审查 ──
    security_level: str = "安全"         # 安全 / 存在潜在风险 / 不安全
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    security_labs: list[dict] = Field(default_factory=list)  # 三线审核标记

    # ── 审查结论 ──
    verdict: str = "通过"                # 通过 / 有条件通过 / 淘汰
    verdict_reason: str = ""             # 结论理由

    # ── 格式修复 ──
    fix_report: FixReportModel = Field(default_factory=FixReportModel)

    # ── 元信息 ──
    files_scanned: int = 0
    total_lines: int = 0
    scan_duration_ms: int = 0


# ═══════════════════════════════════════════════════════
# API 请求/响应
# ═══════════════════════════════════════════════════════

class ScanRequest(BaseModel):
    """扫描请求（文件通过 UploadFile 上传）"""
    pass


class ScanError(BaseModel):
    error: str
    detail: str = ""
