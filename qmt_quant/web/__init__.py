"""Web package."""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "create_app":
        from qmt_quant.web.app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["create_app"]
