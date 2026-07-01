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
from app.engine.skill_fixer import fix_skill_content
from app.models.schemas import FixSkillResponse

router = APIRouter(prefix="", tags=["SkillScan"])


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

    tmp_path = os.path.join(tempfile.gettempdir(), f"skillscan_{uuid.uuid4().hex}.zip")
    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        metadata = {
            "slug": slug or os.path.splitext(file.filename)[0],
            "name": name or "", "category": category or "",
            "stars": stars or 0, "owner_name": author or "",
            "description_zh": description_zh or "",
            "version": version or "", "downloads": downloads or 0,
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

    返回修复后的 SKILL.md 完整内容（字符串），服务器不保存临时文件。
    用户可将返回的 skill_md_content 复制后替换本地文件。
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    slug_val = slug or os.path.splitext(file.filename)[0]
    tmp_path = os.path.join(tempfile.gettempdir(), f"skillscan_fix_{uuid.uuid4().hex}.zip")
    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        report, fixed_content = fix_skill_content(tmp_path)
        return FixSkillResponse(
            slug=slug_val,
            needs_fix=report.needs_fix,
            actions=report.actions,
            errors=report.errors,
            skill_md_content=fixed_content,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "SkillScan TRACE", "version": "2.0.0"}
