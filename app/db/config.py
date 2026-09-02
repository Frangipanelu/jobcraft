"""
JobCraft 数据库配置

提供 SQLAlchemy 引擎、会话工厂和依赖注入。
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# 加载 .env 文件
load_dotenv(override=True)

# 数据库连接 URL
# user/password 必须从环境注入，不提供 root/root 兜底，避免默认弱口令
_db_user = os.getenv("MYSQL_USER")
_db_password = os.getenv("MYSQL_PASSWORD")
DATABASE_URL = f"mysql+mysqlconnector://{_db_user}:{_db_password}@{os.getenv('MYSQL_HOST', 'localhost')}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE', 'jobcraft')}"

# 创建引擎（带连接池）
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),  # 连接池大小
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),  # 最大溢出连接数
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),  # 连接回收时间（秒）
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),  # 连接超时（秒）
    echo=os.getenv("DB_ECHO", "false").lower() == "true",  # 是否打印SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话（FastAPI 依赖注入）

    使用示例：
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items

    :yield: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
