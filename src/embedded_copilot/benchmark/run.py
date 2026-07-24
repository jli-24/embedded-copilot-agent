from __future__ import annotations

import sys


def main() -> int:
    print("benchmark CLI is reserved and not implemented", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
