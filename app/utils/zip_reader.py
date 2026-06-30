"""
安全 zip 读取器 — 仅解压文本文件进行静态分析，绝不执行任何代码
"""
from __future__ import annotations

import zipfile
import re
import os
from typing import Optional
from dataclasses import dataclass, field


# 可扫描文本文件扩展名
SCANNABLE_EXTENSIONS: tuple[str, ...] = (
    ".md", ".py", ".sh", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".txt", ".ps1",
    ".html", ".css", ".xml", ".svg", ".cfg", ".ini", ".conf",
    ".rst", ".csv", ".sql", ".rb", ".go", ".rs", ".java",
    ".kt", ".swift", ".c", ".h", ".cpp", ".hpp",
)

# 二进制文件扩展名 — 绝对不碰
BINARY_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".ogg",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf",
)

# 最大单文件扫描大小 (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

# SKILL.md 文件名变体
SKILL_MD_NAMES: tuple[str, ...] = ("SKILL.md", "skill.md", "README.md")


@dataclass
class ZipFileEntry:
    """zip 内单个文件的信息"""
    path: str
    size: int
    is_text: bool
    is_binary: bool
    is_skill_md: bool
    content: str = ""


@dataclass
class ZipReaderResult:
    """安全读取 zip 的完整结果"""
    slug: str
    zip_path: str
    files: list[ZipFileEntry] = field(default_factory=list)
    skill_md_content: str = ""
    has_binary_files: bool = False
    binary_files: list[str] = field(default_factory=list)
    total_text_files: int = 0
    error: str = ""


def safe_read_zip(zip_path: str, slug: str = "") -> ZipReaderResult:
    """
    安全读取 zip 文件 — 纯静态分析，绝不执行代码

    规则:
    1. 仅解压文本文件（白名单扩展名）
    2. 跳过二进制文件（记录但不上报为错误）
    3. 跳过超大文件 (>5MB)
    4. 优先识别 SKILL.md
    5. 使用 ignore 错误解码，防止编码攻击
    """
    result = ZipReaderResult(slug=slug or os.path.splitext(os.path.basename(zip_path))[0],
                             zip_path=zip_path)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for entry in zf.infolist():
                fname = entry.filename
                # 跳过目录
                if fname.endswith("/"):
                    continue

                ext = os.path.splitext(fname)[1].lower()

                # 跳过二进制文件，记录 R15 检测
                if ext in BINARY_EXTENSIONS or _is_binary_by_name(fname):
                    result.has_binary_files = True
                    result.binary_files.append(fname)
                    entry_info = ZipFileEntry(
                        path=fname, size=entry.file_size,
                        is_text=False, is_binary=True,
                        is_skill_md=False,
                    )
                    result.files.append(entry_info)
                    continue

                # 跳过非文本文件
                if ext not in SCANNABLE_EXTENSIONS:
                    continue

                # 跳过超大文件
                if entry.file_size > MAX_FILE_SIZE:
                    continue

                # 读取文本内容
                try:
                    content = zf.read(entry).decode("utf-8", errors="ignore")
                except Exception:
                    continue

                is_skill_md = os.path.basename(fname) in SKILL_MD_NAMES

                entry_info = ZipFileEntry(
                    path=fname, size=entry.file_size,
                    is_text=True, is_binary=False,
                    is_skill_md=is_skill_md,
                    content=content,
                )

                if is_skill_md:
                    result.skill_md_content = content

                result.files.append(entry_info)
                result.total_text_files += 1

    except zipfile.BadZipFile:
        result.error = "无效的 zip 文件"
    except Exception as e:
        result.error = f"读取 zip 失败: {str(e)}"

    return result


def extract_skill_metadata(skill_md_content: str) -> dict:
    """
    从 SKILL.md 提取元数据（YAML front matter + description）
    仅做文本解析，不执行任何代码
    """
    metadata: dict = {}

    # 尝试提取 YAML front matter
    if skill_md_content.startswith("---"):
        parts = skill_md_content.split("---", 2)
        if len(parts) >= 3:
            yaml_block = parts[1]
            for line in yaml_block.strip().split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        metadata[key] = value

    # 提取 description 字段（`description: ...` 模式）
    desc_match = re.search(
        r'^description:\s*(.+)$', skill_md_content, re.MULTILINE | re.IGNORECASE
    )
    if desc_match:
        metadata.setdefault("description", desc_match.group(1).strip())

    # 提取 name 字段
    name_match = re.search(r'^#+\s*(.+?)$', skill_md_content, re.MULTILINE)
    if name_match:
        metadata.setdefault("title", name_match.group(1).strip())

    return metadata


def _is_binary_by_name(filename: str) -> bool:
    """通过文件名判断是否为二进制/非文本文件"""
    name = os.path.basename(filename).lower()
    return (
        name.startswith(".") and name not in (".gitignore", ".env.example") or
        "node_modules" in filename or
        "__pycache__" in filename or
        ".git/" in filename
    )
