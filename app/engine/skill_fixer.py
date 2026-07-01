"""
SKILL.md 格式检测与自动修复 — 上线前置处理（无需 LLM）

检查项：
  1. 文件名大小写 — 根目录必须有 SKILL.md（大写），skill.md 自动改名
  2. YAML frontmatter 闭合 — 必须有配对的 --- 标记
  3. name / description 字段 — 缺失则从上下文自动补全
  4. version 字段 — 原来没有就不添加

包含两种使用模式：
  - analyze_skill_md() — 仅检测不修改，返回问题列表
  - fix_skill_content() — 执行修复，返回修正后的内容字符串
"""
from __future__ import annotations

import zipfile
import os
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FixReport:
    """格式修正报告"""
    needs_fix: bool = False             # 是否存在需要修复的问题
    actions: list[str] = field(default_factory=list)  # 人类可读的修复描述
    errors: list[str] = field(default_factory=list)   # 错误信息
    extracted_name: str = ""            # 从中提取到的技能名称
    extracted_desc: str = ""            # 从中提取到的技能描述


# SKILL.md 候选文件名（大小写不敏感，根目录级）
SKILL_MD_CANDIDATES = {"SKILL.md", "skill.md", "Skill.md", "SKILL.MD"}
_YAML_DELIM = "---"


# ═══════════════════════════════════════════════════════
# 公共读取：从 zip 中提取 SKILL.md 内容
# ═══════════════════════════════════════════════════════

def read_skill_md_from_zip(zip_path: str) -> tuple[Optional[str], Optional[str], list[str]]:
    """
    读取 zip 中的 SKILL.md 文件内容。

    Returns:
        (original_filename, raw_content, errors)
        - original_filename: zip 内的文件名（如 "skill.md" 或 "SKILL.md"）
        - raw_content: SKILL.md 的文本内容
        - errors: 读取过程中的错误列表
    """
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            entries = list(zf.infolist())
            skill_entry = _find_skill_md(entries)
            if skill_entry is None:
                errors.append("zip 根目录未找到 SKILL.md 文件")
                return None, None, errors
            content = zf.read(skill_entry).decode("utf-8", errors="ignore")
            return skill_entry.filename, content, errors
    except zipfile.BadZipFile:
        errors.append("无效的 zip 文件，无法进行格式修复")
        return None, None, errors
    except Exception as e:
        errors.append(f"读取 zip 失败: {e}")
        return None, None, errors


# ═══════════════════════════════════════════════════════
# 模式 A：仅检测，不修改
# ═══════════════════════════════════════════════════════

def analyze_skill_md(zip_path: str) -> FixReport:
    """
    检测 SKILL.md 的格式问题，不执行任何修复。

    Returns:
        FixReport 包含：
        - needs_fix: 是否存在问题
        - actions:  需要执行的操作描述
        - errors:   严重错误（如文件不存在）
        - extracted_name/extracted_desc: 从现有内容中提取的元数据
    """
    report = FixReport()
    original_filename, raw_content, errors = read_skill_md_from_zip(zip_path)
    report.errors = errors

    if raw_content is None:
        return report

    actions: list[str] = []

    # 1. 文件名大小写
    if original_filename and os.path.basename(original_filename) != "SKILL.md":
        actions.append(f"文件名修正: {original_filename} → SKILL.md")

    # 2. YAML frontmatter 闭合
    if raw_content.startswith(_YAML_DELIM):
        parts = raw_content.split(_YAML_DELIM, 2)
        if len(parts) < 3:
            actions.append("YAML frontmatter 缺少结尾 ---")

    # 3. name / description 字段
    _check_required_fields(raw_content, report)

    if actions:
        report.needs_fix = True
        report.actions = actions

    return report


# ═══════════════════════════════════════════════════════
# 模式 B：检测 + 修复，返回修复后的文本内容
# ═══════════════════════════════════════════════════════

def fix_skill_content(zip_path: str) -> tuple[FixReport, str]:
    """
    检测并修复 SKILL.md，返回修复后的完整内容字符串。

    Returns:
        (FixReport, fixed_content_str)
        - FixReport.needs_fix = True 表示有修复操作
        - fixed_content_str 为修正后的完整 SKILL.md 文本
          如果没有修复必要，则返回原始内容
    """
    report = FixReport()
    original_filename, raw_content, errors = read_skill_md_from_zip(zip_path)
    report.errors = errors

    if raw_content is None:
        return report, ""

    content = raw_content
    need_rewrite = False

    # 1. 文件名大小写修正（只记录，不改变内容）
    filename_fixed = False
    if original_filename and os.path.basename(original_filename) != "SKILL.md":
        report.actions.append(f"文件名修正: {original_filename} → SKILL.md")
        filename_fixed = True
        need_rewrite = True

    # 2. YAML frontmatter 闭合修复
    content, frontmatter_fixed = _fix_yaml_frontmatter(content, report)
    if frontmatter_fixed:
        need_rewrite = True

    # 3. name / description 字段补全
    content, meta_fixed = _ensure_required_fields(content, report)
    if meta_fixed:
        need_rewrite = True

    report.needs_fix = need_rewrite or filename_fixed

    if not need_rewrite:
        # 无修复必要，返回原始内容
        return report, raw_content

    return report, content


# ═══════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════

def _find_skill_md(entries: list[zipfile.ZipInfo]) -> Optional[zipfile.ZipInfo]:
    """在 zip 根目录中查找 SKILL.md（大小写不敏感）"""
    for entry in entries:
        basename = os.path.basename(entry.filename)
        if basename in SKILL_MD_CANDIDATES:
            rel = entry.filename.split("/")
            if len(rel) == 1 or (len(rel) == 2 and rel[0] == ""):
                return entry
    fallback = None
    for entry in entries:
        basename = os.path.basename(entry.filename)
        if basename.lower() == "skill.md":
            if fallback is None:
                fallback = entry
            if "/" not in entry.filename and "\\" not in entry.filename:
                return entry
    return fallback


def _check_required_fields(content: str, report: FixReport) -> None:
    """检查必需的 YAML 字段是否存在，不修改"""
    if not content.startswith(_YAML_DELIM):
        report.extracted_name = ""
        report.extracted_desc = ""
        report.actions.append("缺少 YAML frontmatter 格式")
        return

    parts = content.split(_YAML_DELIM, 2)
    if len(parts) < 3:
        return

    yaml_block = parts[1]
    body = parts[2]
    fields: dict[str, str] = {}
    for line in yaml_block.strip("\n").split("\n"):
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            fields[key.strip().lower()] = value.strip().strip('"').strip("'")

    report.extracted_name = fields.get("name", "")
    report.extracted_desc = fields.get("description", "")

    if not fields.get("name"):
        report.actions.append("YAML frontmatter 缺少 name 字段")
    if not fields.get("description"):
        report.actions.append("YAML frontmatter 缺少 description 字段")


def _fix_yaml_frontmatter(content: str, report: FixReport) -> tuple[str, bool]:
    """修复 YAML frontmatter 闭合问题"""
    lines = content.split("\n")
    if not lines or lines[0].strip() != _YAML_DELIM:
        return content, False

    closing_idx = -1
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped == _YAML_DELIM:
            closing_idx = i
            break

    if closing_idx == -1:
        guess_idx = _guess_frontmatter_end(lines)
        if guess_idx is None:
            return content, False
        lines.insert(guess_idx, _YAML_DELIM)
        report.actions.append("YAML frontmatter 缺少结尾 ---，已自动插入")
        return "\n".join(lines), True

    return content, False


def _guess_frontmatter_end(lines: list[str]) -> Optional[int]:
    """推断 YAML frontmatter 结束位置"""
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            return i
    for i in range(1, len(lines)):
        if lines[i].strip() == "":
            return i
    return 1


def _ensure_required_fields(content: str, report: FixReport) -> tuple[str, bool]:
    """确保 YAML frontmatter 包含 name 和 description"""
    if not content.startswith(_YAML_DELIM):
        return content, False

    parts = content.split(_YAML_DELIM, 2)
    if len(parts) < 3:
        return content, False

    yaml_block = parts[1]
    body = parts[2]
    yaml_lines = yaml_block.strip("\n").split("\n")

    fields: dict[str, str] = {}
    for line in yaml_lines:
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            fields[key.strip().lower()] = value.strip().strip('"').strip("'")

    has_name = "name" in fields and fields["name"] != ""
    has_desc = "description" in fields and fields["description"] != ""

    if has_name and has_desc:
        report.extracted_name = fields.get("name", "")
        report.extracted_desc = fields.get("description", "")
        return content, False

    if not has_name:
        inferred_name = _infer_name(fields, body)
        yaml_lines.append(f"name: {inferred_name}")
        fields["name"] = inferred_name
        report.actions.append(f"YAML frontmatter 缺少 name 字段，已自动补全为: {inferred_name}")

    if not has_desc:
        inferred_desc = _infer_description(fields, body)
        yaml_lines.append(f"description: {inferred_desc}")
        fields["description"] = inferred_desc
        report.actions.append(f"YAML frontmatter 缺少 description 字段，已自动补全")

    report.extracted_name = fields.get("name", "")
    report.extracted_desc = fields.get("description", "")

    new_yaml = "\n".join(yaml_lines)
    return f"{_YAML_DELIM}\n{new_yaml}\n{_YAML_DELIM}{body}", True


def _infer_name(fields: dict[str, str], body: str) -> str:
    title_match = re.search(r"^#\s+(.+?)$", body, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()
    for key in ["slug", "title"]:
        if fields.get(key, ""):
            return fields[key]
    return "Untitled Skill"


def _infer_description(fields: dict[str, str], body: str) -> str:
    found_title = False
    for line in body.split("\n"):
        stripped = line.strip()
        if not found_title and stripped.startswith("#"):
            found_title = True
            continue
        if found_title and stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:200]
    return fields.get("name", "技能描述待补充")
