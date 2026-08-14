"""MySQL Session Store — 使用 SQLAlchemy ORM 持久化会话。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.models.database import SessionLocal
from app.models.orm import AnalysisSession, ResumeVersion, UploadedFile
from app.models.session_store import SessionStore

logger = logging.getLogger(__name__)


class MySQLSessionStore(SessionStore):
    """MySQL 会话存储（生产环境用）。"""

    def __init__(self, db_factory=None) -> None:
        self._db_factory = db_factory or SessionLocal

    def _get_db(self) -> DBSession:
        return self._db_factory()

    async def create(self, session_id: str, data: dict[str, Any]) -> None:
        db = self._get_db()
        try:
            session = AnalysisSession(
                session_id=session_id,
                stage=data.get("stage", "init"),
                created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            )
            db.add(session)
            db.commit()
            logger.info(f"MySQL: Created session {session_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"MySQL: Failed to create session {session_id}: {e}")
            raise
        finally:
            db.close()

    async def get(self, session_id: str) -> dict[str, Any] | None:
        db = self._get_db()
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            if session is None:
                return None
            return self._session_to_dict(session, db)
        finally:
            db.close()

    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        db = self._get_db()
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            if session is None:
                return

            # 更新基本字段
            if "stage" in data:
                session.stage = data["stage"]
            if "jd_analysis" in data:
                session.jd_analysis_json = json.dumps(data["jd_analysis"], ensure_ascii=False)
            if "profile" in data:
                session.profile_json = json.dumps(data["profile"], ensure_ascii=False)
            if "gap_analysis" in data:
                session.gap_analysis_json = json.dumps(data["gap_analysis"], ensure_ascii=False)
            if "render_config" in data:
                session.render_config_json = json.dumps(data["render_config"], ensure_ascii=False)

            session.updated_at = datetime.now()

            # 处理上传文件
            if "uploaded_files" in data:
                for file_info in data["uploaded_files"]:
                    # 检查是否已存在
                    existing = db.query(UploadedFile).filter(
                        UploadedFile.session_id == session_id,
                        UploadedFile.file_path == file_info.get("file_path", "")
                    ).first()
                    if not existing:
                        uploaded = UploadedFile(
                            session_id=session_id,
                            filename=file_info.get("filename", ""),
                            file_type=file_info.get("file_type", ""),
                            file_path=file_info.get("file_path", ""),
                            file_size=file_info.get("file_size", 0),
                        )
                        db.add(uploaded)

            # 处理简历版本
            if "resume_content" in data and data["resume_content"]:
                # 获取当前最大版本号
                max_version = db.query(ResumeVersion).filter(
                    ResumeVersion.session_id == session_id
                ).count()
                version = ResumeVersion(
                    session_id=session_id,
                    version=max_version + 1,
                    content_json=json.dumps(data["resume_content"], ensure_ascii=False),
                    render_config_json=json.dumps(data.get("render_config", {}), ensure_ascii=False) if data.get("render_config") else None,
                )
                db.add(version)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"MySQL: Failed to update session {session_id}: {e}")
            raise
        finally:
            db.close()

    async def delete(self, session_id: str) -> bool:
        db = self._get_db()
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            if session is None:
                return False
            db.delete(session)
            db.commit()
            logger.info(f"MySQL: Deleted session {session_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"MySQL: Failed to delete session {session_id}: {e}")
            raise
        finally:
            db.close()

    async def exists(self, session_id: str) -> bool:
        db = self._get_db()
        try:
            count = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).count()
            return count > 0
        finally:
            db.close()

    def _session_to_dict(self, session: AnalysisSession, db: DBSession) -> dict[str, Any]:
        """将 ORM 对象转换为字典。"""
        # 获取上传文件
        uploaded_files = []
        for f in session.uploaded_files:
            uploaded_files.append({
                "filename": f.filename,
                "file_type": f.file_type,
                "file_path": f.file_path,
                "file_size": f.file_size,
                "uploaded_at": f.created_at.isoformat() if f.created_at else None,
            })

        # 获取最新简历版本
        resume_content = None
        render_config = None
        if session.resume_versions:
            latest = max(session.resume_versions, key=lambda v: v.version)
            resume_content = json.loads(latest.content_json)
            if latest.render_config_json:
                render_config = json.loads(latest.render_config_json)

        return {
            "session_id": session.session_id,
            "stage": session.stage,
            "messages": [],  # 消息历史存在 Redis 中
            "jd_analysis": json.loads(session.jd_analysis_json) if session.jd_analysis_json else None,
            "profile": json.loads(session.profile_json) if session.profile_json else None,
            "gap_analysis": json.loads(session.gap_analysis_json) if session.gap_analysis_json else None,
            "resume_content": resume_content,
            "render_config": render_config if render_config else (json.loads(session.render_config_json) if session.render_config_json else None),
            "interview_questions": None,  # 暂不持久化面试题
            "uploaded_files": uploaded_files,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
