"""
环境变量加载器 — 从 .env.{APP_ENV} 文件读取配置

策略：
  1. 检查环境变量 APP_ENV（dev / test / prod），默认 dev
  2. 读取与 `app/` 同级的 `.env.{APP_ENV}` 文件
  3. 不覆盖已存在的环境变量（os.environ 优先级更高）
  4. 文件路径使用相对路径计算，支持作为子目录挂载
"""
from __future__ import annotations
import os
import logging

logger = logging.getLogger("skillscan.env")


def _get_project_root() -> str:
    """返回项目根目录（app/ 的父目录），使用相对路径"""
    # app/env_loader.py → app/ → 项目根目录
    current = os.path.dirname(os.path.abspath(__file__))   # app/
    return os.path.dirname(current)                         # 项目根


def load_env() -> None:
    """加载对应环境的 .env 文件到 os.environ"""
    app_env = os.environ.get("APP_ENV", "dev")               # 默认 dev
    root = _get_project_root()
    env_file = os.path.join(root, f".env.{app_env}")
    example_file = os.path.join(root, ".env.example")

    if not os.path.exists(env_file):
        logger.warning(f"环境配置文件不存在: {env_file}，尝试加载 .env.example")
        env_file = example_file if os.path.exists(example_file) else None

    if env_file is None:
        logger.info("未找到任何 .env 文件，使用默认值")
        return

    loaded = 0
    skipped = 0
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # 跳过空行和注释
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue

            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if not key:
                continue

            # 不覆盖已存在的环境变量
            if key in os.environ:
                skipped += 1
                continue

            os.environ[key] = value
            loaded += 1

    logger.info(f"已加载 {env_file}: {loaded} 个变量{', 跳过 ' + str(skipped) + ' 个已存在的' if skipped else ''}")
    os.environ.setdefault("APP_ENV", app_env)


# 模块导入时自动加载
load_env()
