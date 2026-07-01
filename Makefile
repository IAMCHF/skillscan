# ═══════════════════════════════════════════════════════
# SkillScan Makefile — 多环境启动
# ═══════════════════════════════════════════════════════
#
# 用法:
#   make dev      — 开发环境（默认，.env.dev）
#   make test     — 测试环境（.env.test）
#   make prod     — 生产环境（.env.prod）
#   make clean    — 清理临时文件
#   make install  — 安装依赖
#
# 注意: 在 Windows 上使用 `make` 需要安装 GNU Make 或
#       使用 Chocolatey (choco install make)。
#       也可直接运行:
#         uvicorn app.main:app --host 0.0.0.0 --port 8000
#       此时需自行设置 os.environ 或在同目录放 .env.dev
# ═══════════════════════════════════════════════════════

APP_ENV ?= dev
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: dev test prod clean install

dev:
	APP_ENV=dev \
	uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

test:
	APP_ENV=test \
	uvicorn app.main:app --host $(HOST) --port $(PORT)

prod:
	APP_ENV=prod \
	uvicorn app.main:app --host $(HOST) --port $(PORT) --workers 4

install:
	pip install -r requirements.txt

clean:
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf .mypy_cache
