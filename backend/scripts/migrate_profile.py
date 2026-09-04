"""CLI: 迁移 career_profiles.profile_json → ProfileItem + Evidence.

用法（在 backend/ 目录下）：
    python -m scripts.migrate_profile --dry-run
    python -m scripts.migrate_profile --apply
"""

from __future__ import annotations

import argparse
import sys

from app.services.profile_migration import apply_migration, plan_migration


def _print_plan(plan) -> None:
    if not plan:
        print("无待迁移的 career_profile（或均已迁移）。")
        return
    for entry in plan:
        print(f"[user_id={entry['user_id']}] source={entry['source']} -> {len(entry['items'])} 条")
        for it in entry["items"]:
            content_preview = (it["content"] or "")[:60].replace("\n", " | ")
            print(f"    - [{it['category']}/{it['status']}] {it['title']}: {content_preview}")


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 career_profiles 到条目级 ProfileItem")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    parser.add_argument("--apply", action="store_true", help="执行写入")
    args = parser.parse_args()

    from app.models.database import SessionLocal

    db = SessionLocal()
    try:
        if args.apply:
            plan = apply_migration(db)
            print(f"已迁移 {len(plan)} 个用户画像为条目级 ProfileItem。")
            _print_plan(plan)
        else:
            plan = plan_migration(db)
            _print_plan(plan)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
