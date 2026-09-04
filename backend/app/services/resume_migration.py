"""resume_versions 旧数据 → 简历库资产的增量迁移（阶段2 指令2-1）。

两件事：
1. 列变更（仅 MySQL）：resume_versions 增加 document_id / user_id 列、session_id 改可空。
   新表 resume_documents / resume_sections 由启动 create_all 自动建，无需处理。
2. 数据回填：按会话把已存的 resume_versions 挂到新建的 ResumeDocument 下（每会话一文档），
   最新版本设为当前版本。无 user_id 的匿名会话跳过（文档必须归属用户）。

CLI：scripts/migrate_resume_library.py（--dry-run / --apply，幂等）。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from app.models.orm import AnalysisSession, ResumeDocument, ResumeVersion

logger = logging.getLogger(__name__)

# 列存在性检查 + 变更语句（仅 MySQL 执行；SQLite 测试库由 create_all 直接带全量列）
_REQUIRED_COLUMNS = {
    "document_id": "ALTER TABLE resume_versions ADD COLUMN document_id INT NULL",
    "user_id": "ALTER TABLE resume_versions ADD COLUMN user_id INT NULL",
}


def _is_mysql(db: DBSession) -> bool:
    return db.bind is not None and db.bind.dialect.name == "mysql"


def _column_exists(db: DBSession, table: str, column: str) -> bool:
    sql = text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column"
    )
    return bool(db.execute(sql, {"table": table, "column": column}).scalar())


def plan_column_changes(db: DBSession) -> list[str]:
    """返回待执行的 ALTER 语句（MySQL 专用；其它方言返回空）。"""
    if not _is_mysql(db):
        return []
    statements: list[str] = []
    for column, ddl in _REQUIRED_COLUMNS.items():
        if not _column_exists(db, "resume_versions", column):
            statements.append(ddl)
    # session_id 由 NOT NULL 改为 NULL（旧行不受影响，新库版本可脱离会话存在）
    if _column_exists(db, "resume_versions", "session_id"):
        statements.append("ALTER TABLE resume_versions MODIFY session_id VARCHAR(36) NULL")
    return statements


def plan_backfill(db: DBSession) -> tuple[list[dict[str, Any]], int]:
    """返回 (待回填计划, 跳过的匿名会话数)。幂等：只统计 document_id IS NULL 的版本。"""
    rows = (
        db.query(ResumeVersion.session_id)
        .filter(ResumeVersion.document_id.is_(None), ResumeVersion.session_id.isnot(None))
        .distinct()
        .all()
    )
    plan: list[dict[str, Any]] = []
    skipped = 0
    for (session_id,) in rows:
        session = db.query(AnalysisSession).filter(AnalysisSession.session_id == session_id).first()
        user_id = session.user_id if session else None
        if not user_id:
            skipped += 1
            continue
        version_count = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.session_id == session_id, ResumeVersion.document_id.is_(None))
            .count()
        )
        plan.append(
            {
                "session_id": session_id,
                "user_id": int(user_id),
                "version_count": version_count,
                "title": f"会话简历 {session_id[:8]}",
            }
        )
    return plan, skipped


def apply_migration(db: DBSession) -> dict[str, Any]:
    """执行列变更 + 回填，返回摘要。"""
    columns_added = 0
    statements = plan_column_changes(db)
    for ddl in statements:
        db.execute(text(ddl))
        columns_added += 1
        logger.info("resume 迁移 DDL: %s", ddl)
    db.commit()

    plan, skipped = plan_backfill(db)
    docs_created = 0
    versions_linked = 0
    for entry in plan:
        doc = ResumeDocument(
            user_id=entry["user_id"],
            title=entry["title"],
            source="session",
        )
        db.add(doc)
        db.flush()
        versions = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.session_id == entry["session_id"], ResumeVersion.document_id.is_(None))
            .order_by(ResumeVersion.id.asc())
            .all()
        )
        latest: ResumeVersion | None = None
        for idx, version in enumerate(versions, start=1):
            version.document_id = doc.id
            version.user_id = entry["user_id"]
            version.version = idx
            latest = version
            versions_linked += 1
        if latest is not None:
            doc.current_version_id = latest.id
        docs_created += 1
    db.commit()
    return {
        "columns_added": columns_added,
        "ddl": statements,
        "docs_created": docs_created,
        "versions_linked": versions_linked,
        "anonymous_sessions_skipped": skipped,
    }
