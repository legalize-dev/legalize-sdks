"""Time-travel: retrieve a law's full text at a historical git commit.

Usage::

    LEGALIZE_API_KEY=leg_... python examples/time_travel.py es ley_organica_3_2018
"""

from __future__ import annotations

import os
import sys

from legalize import Legalize


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: time_travel.py <country> <law_id>", file=sys.stderr)
        return 2
    country, law_id = sys.argv[1], sys.argv[2]

    with Legalize(api_key=os.environ["LEGALIZE_API_KEY"]) as client:
        commits = client.laws.commits(country=country, law_id=law_id)
        print(f"{len(commits.commits)} commits for {law_id}\n")
        for _i, c in enumerate(commits.commits[:5]):
            print(f"  {c.sha[:10]}  {c.date}  {c.message.splitlines()[0][:60]}")

        if not commits.commits:
            return 0

        # Show the first historical version.
        oldest = commits.commits[-1]
        print(f"\n--- {law_id} at {oldest.sha[:10]} ({oldest.date}) ---\n")
        snapshot = client.laws.at_commit(country=country, law_id=law_id, sha=oldest.sha)
        print(snapshot.content_md[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
