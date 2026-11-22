"""``python -m pwb_toolbox.docs [page]``: print a documentation page (default ``backtesting``)."""

import sys

from . import pages, read


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    name = argv[0] if argv else "backtesting"
    try:
        sys.stdout.write(read(name))
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
