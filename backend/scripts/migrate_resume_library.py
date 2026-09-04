"""CLI: resume_versions 旧数据 → 简历库资产（ResumeDocument）增量迁移.

用法（在 backend/ 目录下）：
    python -m scripts.migrate_resume_library --dry-run
    python -m scripts.migrate_resume_library --apply
"""

from __future__ import annotations

import argparse
import sys

from app.services.resume_migration import apply_migration, plan_backfill, plan_column_changes


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 resume_versions 旧数据到简历库文档")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    parser.add_argument("--apply", action="store_true", help="执行写入")
    args = parser.parse_args()

    from app.models.database import SessionLocal

    db = SessionLocal()
    try:
        ddl = plan_column_changes(db)
        plan, skipped = plan_backfill(db)
        if args.apply:
            summary = apply_migration(db)
            print(
                f"迁移完成：DDL {summary['columns_added']} 条，"
                f"创建文档 {summary['docs_created']} 个，挂接版本 {summary['versions_linked']} 版，"
                f"跳过匿名会话 {summary['anonymous_sessions_skipped']} 个。"
            )
        else:
            print(f"待执行 DDL（仅 MySQL）：{len(ddl)} 条")
            for stmt in ddl:
                print(f"    {stmt}")
            print(f"待回填会话 {len(plan)} 个（跳过匿名 {skipped} 个）：")
            for entry in plan:
                print(f"    [user_id={entry['user_id']}] {entry['session_id']} -> {entry['version_count']} 版 ({entry['title']})")
            if not ddl and not plan:
                print("无待迁移内容。")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
