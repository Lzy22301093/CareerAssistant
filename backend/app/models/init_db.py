"""Database initialization script.

Run this script to create all database tables:
    python -m app.models.init_db
"""

import logging

from app.models.database import Base, engine
from app.models.orm import (  # noqa: F401
    AnalysisSession,
    CareerProfile,
    InterviewLog,
    InterviewReport,
    JobApplication,
    JobPosting,
    MatchTask,
    ProfileEvidence,
    ProfileItem,
    ProfileUpdateProposal,
    ResumeDocument,
    ResumeSection,
    ResumeVersion,
    UploadedFile,
    User,
    UserPreference,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database() -> None:
    """Create all database tables."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


if __name__ == "__main__":
    init_database()
