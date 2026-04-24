"""pnfl-scheduler package."""


def main(argv=None):
    from .cli import main as _main

    return _main(argv)


__all__ = [
    "main",
]
