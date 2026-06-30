"""
FastAPI 应用入口 — SkillScan TRACE 审核服务
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.scan import router as scan_router

app = FastAPI(
    title="SkillScan TRACE",
    description="企业内网 AI 技能静态安全审核服务。基于 LLM + SkillHub TRACE 五维度评测体系，纯静态分析不执行代码。",
    version="2.0.0",
    docs_url="/docs",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(scan_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
