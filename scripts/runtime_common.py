"""Stable UTF-8 CLI output on Windows as well as cloud/Linux hosts."""
import sys


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
