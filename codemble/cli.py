"""Codemble CLI entrypoint. Usage (target): `codemble ./my-project`.

Milestone M1 (see CLAUDE.md) implements the parser; this stub only proves the
package wiring and version plumbing.
"""

import sys

from codemble import __version__


def main() -> int:
    if "--version" in sys.argv:
        print(f"codemble {__version__}")
        return 0
    print("Codemble is under construction - Phase 0, milestone M1 (parser & graph).")
    print("Follow along: https://github.com/udhawan97/Codemble")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
