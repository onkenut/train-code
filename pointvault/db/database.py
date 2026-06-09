"""
数据库连接管理 - SQLAlchemy 2.0 + SQLite WAL 模式
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from pointvault.db.models import Base


class Database:
    """单例数据库管理器"""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path: Optional[Path] = Path(db_path) if db_path else None
        self._engine: Optional[Engine] = None
        self._SessionLocal: Optional[sessionmaker] = None
        self._initialized = False

    # ---------- 单例 ----------
    @classmethod
    def instance(cls) -> "Database":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ---------- 生命周期 ----------
    def connect(self, db_path: Path | str) -> None:
        """连接到指定的 SQLite 数据库文件"""
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        db_url = f"sqlite:///{self._db_path.resolve().as_posix()}"
        self._engine = create_engine(
            db_url,
            echo=False,
            future=True,
            connect_args={
                "check_same_thread": False,
                "timeout": 30.0,
            },
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        @event.listens_for(self._engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            """启用 WAL 模式与外键约束"""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA cache_size=-65536;")  # 64MB page cache
            cursor.execute("PRAGMA temp_store=MEMORY;")
            cursor.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap
            cursor.close()

        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
        self._initialized = True

    def create_tables(self) -> None:
        """创建所有表结构"""
        if self._engine is None:
            raise RuntimeError("Database not connected")
        Base.metadata.create_all(bind=self._engine)

    def disconnect(self) -> None:
        """断开数据库连接"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._SessionLocal = None
            self._initialized = False
            self._db_path = None

    # ---------- Session ----------
    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("Database not connected")
        return self._engine

    @property
    def db_path(self) -> Optional[Path]:
        return self._db_path

    def session(self) -> Session:
        if self._SessionLocal is None:
            raise RuntimeError("Database not initialized")
        return self._SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """线程安全的事务上下文管理器"""
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def vacuum(self) -> None:
        """VACUUM 压缩数据库"""
        if self._engine is None:
            return
        with self._engine.connect() as conn:
            conn.execute(text("VACUUM;"))
            conn.commit()


# ---------- 便捷函数 ----------
def init_db(db_path: Path | str) -> Database:
    """初始化并返回全局数据库实例"""
    db = Database.instance()
    db.connect(db_path)
    db.create_tables()
    return db


def get_session() -> Session:
    """获取当前全局数据库的 Session"""
    return Database.instance().session()
