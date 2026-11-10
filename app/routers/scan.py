"""
SkillScan API — 单技能 TRACE 审核 + SKILL.md 格式修复

POST /scan       — TRACE 审核单个技能（格式检测不通过则立即返回）
POST /fix-skill  — 检测并修复 SKILL.md，返回修复后的内容（不保存临时文件）
GET  /health     — 健康检查
"""
from __future__ import annotations
import os, uuid, tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional

from app.engine.scanner import scan_single_skill
from app.engine.skill_fixer import fix_skill_zip
from app.models.schemas import FixSkillResponse

router = APIRouter(prefix="", tags=["SkillScan"])

# 最大上传文件大小 (50MB)，防止超大文件占满内存
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


async def _save_upload_to_tmp(file: UploadFile, prefix: str) -> str:
    """流式保存上传文件到临时路径，超过大小限制立即终止"""
    tmp_path = os.path.join(tempfile.gettempdir(), f"{prefix}_{uuid.uuid4().hex}.zip")
    size = 0
    with open(tmp_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail="文件过大，最大支持 50MB")
            f.write(chunk)
    return tmp_path


@router.post("/scan", summary="TRACE 审核单个技能")
async def scan_skill(
    file: UploadFile = File(..., description="技能 .zip 文件"),
    slug: Optional[str] = Query(None, description="技能 slug"),
    name: Optional[str] = Query(None, description="技能名称"),
    category: Optional[str] = Query(None, description="原始分类"),
    stars: Optional[int] = Query(None, description="星标数"),
    author: Optional[str] = Query(None, description="作者"),
    description_zh: Optional[str] = Query(None, description="中文描述"),
    version: Optional[str] = Query(None, description="版本号"),
    downloads: Optional[int] = Query(None, description="下载量"),
    updated_at: Optional[str] = Query(None, description="更新时间"),
):
    """
    上传单个技能 zip，执行 TRACE 五维度静态分析。

    先检测 SKILL.md 格式，发现问题则立即返回（淘汰），
    不执行 TRACE 评测。请先通过 /fix-skill 修复格式后重试。
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    tmp_path = await _save_upload_to_tmp(file, "skillscan")
    try:
        metadata = {
            "slug": slug or os.path.splitext(file.filename)[0],
            "name": name or "",
            "category": category or "",
            "stars": stars or 0,
            "owner_name": author or "",
            "description_zh": description_zh or "",
            "version": version or "",
            "downloads": downloads or 0,
            "updated_at": updated_at or "",
        }
        return await scan_single_skill(tmp_path, metadata)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/fix-skill", summary="检测并修复 SKILL.md 格式")
async def fix_skill(
    file: UploadFile = File(..., description="技能 .zip 文件"),
    slug: Optional[str] = Query(None, description="技能 slug"),
):
    """
    上传技能 zip，检测 SKILL.md 格式问题并自动修复。

    返回修复后的 SKILL.md 完整内容和修复后的 zip 文件（base64 编码）。
    修复项包括：
    1. SKILL.md 文件名大小写
    2. YAML frontmatter 闭合
    3. name/description 字段补全
    4. **zip 目录结构**（SKILL.md 移动到根目录）
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    slug_val = slug or os.path.splitext(file.filename)[0]
    tmp_path: Optional[str] = None
    fixed_zip_path = None

    try:
        tmp_path = await _save_upload_to_tmp(file, "skillscan_fix")

        report, fixed_content, fixed_zip_path = fix_skill_zip(tmp_path)

        # 如果有修复后的 zip 文件，进行 base64 编码
        fixed_zip_base64 = None
        if fixed_zip_path and os.path.exists(fixed_zip_path):
            with open(fixed_zip_path, "rb") as f:
                import base64
                fixed_zip_base64 = base64.b64encode(f.read()).decode("utf-8")

        return FixSkillResponse(
            slug=slug_val,
            needs_fix=report.needs_fix,
            actions=report.actions,
            errors=report.errors,
            skill_md_content=fixed_content,
            fixed_zip_base64=fixed_zip_base64 or "",
        )

    finally:
        # 清理临时文件
        for path in [tmp_path, fixed_zip_path]:
            if path and os.path.exists(path):
                os.remove(path)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "SkillScan TRACE", "version": "2.0.0"}
