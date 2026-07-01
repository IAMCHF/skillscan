"""
SKILL.md 格式检测与自动修复 — 上线前置处理（无需 LLM）

检查项：
  1. 文件名大小写 — 根目录必须有 SKILL.md（大写），skill.md 自动改名
  2. YAML frontmatter 闭合 — 必须有配对的 --- 标记
  3. name / description 字段 — 缺失则从上下文自动补全
  4. version 字段 — 原来没有就不添加

修正后写入新 zip，返回修正后的 zip 路径 + 修正报告。
"""
from __future__ import annotations

import zipfile
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FixReport:
    """格式修正报告"""
    zip_fixed: bool = False             # 是否执行了任何修复
    original_path: str = ""
    fixed_path: str = ""                # 修复后的 zip 路径
    actions: list[str] = field(default_factory=list)  # 人类可读的修复描述
    errors: list[str] = field(default_factory=list)
    extracted_name: str = ""            # 从修复中提取到的技能名称
    extracted_desc: str = ""            # 从修复中提取到的技能描述


# SKILL.md 候选文件名（大小写不敏感，根目录级）
SKILL_MD_CANDIDATES = {"SKILL.md", "skill.md", "Skill.md", "SKILL.MD"}


def fix_skill_zip(original_path: str) -> FixReport:
    """
    检测并修复 zip 包内 SKILL.md 的格式问题，返回修复后的 zip 路径。

    不修改原始文件，生成新的临时 zip。
    """
    report = FixReport(original_path=original_path)

    try:
        with zipfile.ZipFile(original_path, "r") as zf:
            entries = list(zf.infolist())
    except zipfile.BadZipFile:
        report.errors.append("无效的 zip 文件，无法进行格式修复")
        report.fixed_path = original_path
        return report
    except Exception as e:
        report.errors.append(f"读取 zip 失败: {e}")
        report.fixed_path = original_path
        return report

    # ── 1. 查找根目录 SKILL.md ──
    skill_entry = _find_skill_md(entries)
    if skill_entry is None:
        report.errors.append("zip 根目录未找到 SKILL.md 文件")
        report.fixed_path = original_path
        return report

    raw_content = zf.read(skill_entry).decode("utf-8", errors="ignore")
    original_filename = skill_entry.filename

    content = raw_content
    need_rewrite = False

    # ── 2. 文件名大小写修正 ──
    fixed_filename = os.path.basename(original_filename)
    if fixed_filename != "SKILL.md":
        report.actions.append(f"文件名修正: {original_filename} → SKILL.md")
        fixed_filename = "SKILL.md"
        need_rewrite = True

    # ── 3. YAML frontmatter 闭合检查与修复 ──
    content, frontmatter_fixed = _fix_yaml_frontmatter(content, report)
    if frontmatter_fixed:
        need_rewrite = True

    # ── 4. name / description 字段补全 ──
    content, meta_fixed = _ensure_required_fields(content, report)
    if meta_fixed:
        need_rewrite = True

    # ── 5. 写回修复后的 zip ──
    if not need_rewrite:
        report.fixed_path = original_path
        return report

    report.zip_fixed = True
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="skillscan_fixed_")
    os.close(tmp_fd)

    with zipfile.ZipFile(original_path, "r") as zin:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for entry in zin.infolist():
                if entry.filename == original_filename:
                    # 用修正后的内容和文件名替换
                    zout.writestr(zipfile.ZipInfo(fixed_filename), content.encode("utf-8"))
                else:
                    zout.writestr(entry, zin.read(entry.filename))

    report.fixed_path = tmp_path
    return report


# ═══════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════

def _find_skill_md(entries: list[zipfile.ZipInfo]) -> Optional[zipfile.ZipInfo]:
    """在 zip 根目录中查找 SKILL.md（大小写不敏感）"""
    for entry in entries:
        basename = os.path.basename(entry.filename)
        if basename in SKILL_MD_CANDIDATES:
            # 确认是根目录（路径不包含子目录分隔符）
            rel = entry.filename.split("/")
            if len(rel) == 1 or (len(rel) == 2 and rel[0] == ""):
                return entry
    # 宽松匹配：任何路径下的 skill.md / SKILL.md
    fallback = None
    for entry in entries:
        basename = os.path.basename(entry.filename)
        if basename.lower() == "skill.md":
            if fallback is None:
                fallback = entry
            # 根目录优先
            if "/" not in entry.filename and "\\" not in entry.filename:
                return entry
    return fallback


_YAML_DELIM = "---"


def _fix_yaml_frontmatter(content: str, report: FixReport) -> tuple[str, bool]:
    """
    修复 YAML frontmatter 闭合问题。

    常见错误:
      - 只有开头的 ---，缺少结尾的 ---
      - 结尾 --- 前面有非法缩进
      - 正文第一个 # 标题被吞进 YAML 块

    Returns (fixed_content, has_changes)
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != _YAML_DELIM:
        return content, False  # 没有 frontmatter，不处理

    # 查找第二个 ---
    closing_idx = -1
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped == _YAML_DELIM:
            closing_idx = i
            break

    if closing_idx == -1:
        # 缺结尾 ---，尝试自动推断位置并插入
        guess_idx = _guess_frontmatter_end(lines)
        if guess_idx is None:
            return content, False

        # 插入结尾 ---
        lines.insert(guess_idx, _YAML_DELIM)
        report.actions.append("YAML frontmatter 缺少结尾 ---，已自动插入")
        return "\n".join(lines), True

    return content, False


def _guess_frontmatter_end(lines: list[str]) -> Optional[int]:
    """
    推断 YAML frontmatter 应该在哪个位置结束。

    策略:
      1. 找到第一个 `#` 开头的 markdown 标题行 → 在它前面插入
      2. 没有标题 → 在第一个空行之后插入
      3. 否则在开头的 --- 后面 1 行插入（极端情况）
    """
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("#"):
            return i

    # 找第一个纯空行
    for i in range(1, len(lines)):
        if lines[i].strip() == "":
            return i

    # 兜底：第 2 行插入
    return 1


def _ensure_required_fields(content: str, report: FixReport) -> tuple[str, bool]:
    """
    确保 YAML frontmatter 包含 name 和 description。
    原来没有 version 就不添加 version。
    """
    if not content.startswith(_YAML_DELIM):
        return content, False

    parts = content.split(_YAML_DELIM, 2)
    if len(parts) < 3:
        return content, False

    yaml_block = parts[1]
    body = parts[2]
    yaml_lines = yaml_block.strip("\n").split("\n")

    # 解析现有字段
    fields: dict[str, str] = {}
    for line in yaml_lines:
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            fields[key.strip().lower()] = value.strip().strip('"').strip("'")

    has_name = "name" in fields and fields["name"] != ""
    has_desc = "description" in fields and fields["description"] != ""

    if has_name and has_desc:
        # 从修复过程中提取元数据
        report.extracted_name = fields.get("name", "")
        report.extracted_desc = fields.get("description", "")
        return content, False

    # 补全缺失字段
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

    # 重新组装
    new_yaml = "\n".join(yaml_lines)
    return f"{_YAML_DELIM}\n{new_yaml}\n{_YAML_DELIM}{body}", True


def _infer_name(fields: dict[str, str], body: str) -> str:
    """推断技能名称"""
    # 1. 从 markdown 第一个标题
    title_match = re.search(r"^#\s+(.+?)$", body, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()

    # 2. 从 slug 类字段
    for key in ["slug", "title"]:
        if fields.get(key, ""):
            return fields[key]

    return "Untitled Skill"


def _infer_description(fields: dict[str, str], body: str) -> str:
    """推断技能描述"""
    # 1. 标题后的第一段非空文本
    found_title = False
    for line in body.split("\n"):
        stripped = line.strip()
        if not found_title and stripped.startswith("#"):
            found_title = True
            continue
        if found_title and stripped and not stripped.startswith("#") and not stripped.startswith(">"):
            return stripped[:200]
    # 2. 兜底
    return fields.get("name", "技能描述待补充")
