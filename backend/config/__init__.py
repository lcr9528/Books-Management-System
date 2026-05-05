"""
在 Django 加载 mysql 后端之前，把 PyMySQL 注册为 MySQLdb。
必须在读取 MYSQL_* 之前加载 .env（settings 里的 load_dotenv 执行得更晚）。
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _base = Path(__file__).resolve().parent.parent
    load_dotenv(_base / ".env", override=False)
except ImportError:
    pass

if os.environ.get("MYSQL_DATABASE"):
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError as exc:
        raise ImportError(
            "已配置 MYSQL_DATABASE，但未安装 PyMySQL。请在虚拟环境中执行：pip install PyMySQL"
        ) from exc
