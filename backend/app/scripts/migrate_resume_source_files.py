"""增量迁移：创建 resume_source_files（上传原件，Word 保版导出）。

用法：
  python -m app.scripts.migrate_resume_source_files           # dry-run
  python -m app.scripts.migrate_resume_source_files --apply
"""

from __future__ import annotations

import sys

from app.models.database import Base, engine
from app.models.orm import ResumeSourceFile  # noqa: F401  触发注册


def main() -> None:
    apply = "--apply" in sys.argv
    tables = list(Base.metadata.tables.keys())
    print(f"将确保建表: resume_source_files（metadata 共 {len(tables)} 表）")
    if not apply:
        print("dry-run：未执行。加 --apply 实际 CREATE TABLE IF NOT EXISTS。")
        return
    # create_all 幂等，只建缺失表
    Base.metadata.create_all(bind=engine, tables=[ResumeSourceFile.__table__])
    print("已创建/确认 resume_source_files")


if __name__ == "__main__":
    main()
