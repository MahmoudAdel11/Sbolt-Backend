#!/usr/bin/env python3
"""Local-development-only cleanup for accumulated test ride data.

Deletes every row from the `rides` table so repeated manual testing sessions
don't keep accumulating stale REQUESTED/ACCEPTED rides that show up as
confusing "phantom" rides later. Full-table, not "non-terminal only" - once
a session's ride flow has been manually verified, its completed history has
no further test value, and deleting everything gives a predictable clean
slate rather than a partially-reset one. If you want to keep completed
history around, don't run this.

Does NOT touch users, driver_profiles, or favorite_places - only `rides`.

Deliberately NOT an API endpoint - this must never be reachable from a
running server in any environment. It's a standalone script, run by hand:

    python scripts/reset_dev_data.py          # interactive y/N prompt
    python scripts/reset_dev_data.py --yes    # skip the prompt

Refuses to run unless the configured DATABASE_URL points at
localhost/127.0.0.1/::1 - this must be impossible to accidentally run
against a real deployment.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_local_database(database_url: str) -> None:
    """Hard-stops the script unless the DB host is unambiguously local.

    This is the one thing standing between this script and accidentally
    wiping ride data on a real deployment - it must fail closed.
    """
    host = make_url(database_url).host
    if host not in _LOCAL_HOSTS:
        print(
            f"Refusing to run: DATABASE_URL host is '{host}', not one of "
            f"{sorted(_LOCAL_HOSTS)}. This script only runs against a local "
            "dev database.",
            file=sys.stderr,
        )
        sys.exit(1)


async def _delete_all_rides(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("DELETE FROM rides"))
            return result.rowcount
    finally:
        await engine.dispose()


def _confirm(skip_prompt: bool) -> bool:
    if skip_prompt:
        return True
    answer = input(
        "This will permanently delete ALL rows from the 'rides' table in "
        "the local dev database. Continue? [y/N] "
    )
    return answer.strip().lower() in ("y", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete all rows from the local dev database's 'rides' table."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    args = parser.parse_args()

    database_url = get_settings().database_url
    _assert_local_database(database_url)

    url = make_url(database_url)
    print(f"Target database: {url.database!r} on {url.host}")

    if not _confirm(args.yes):
        print("Aborted - no changes made.")
        sys.exit(0)

    deleted = asyncio.run(_delete_all_rides(database_url))
    print(
        f"Deleted {deleted} row(s) from 'rides'. "
        "users, driver_profiles, and favorite_places were not touched."
    )


if __name__ == "__main__":
    main()
