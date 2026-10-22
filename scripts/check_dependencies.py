#!/usr/bin/env python3
"""Read-only runtime check. No installations, uploads or external services."""
import importlib
import json
import shutil
import sys
from runtime_common import configure_stdio


def inspect():
    modules = {}
    for name in ("pymupdf", "docx"):
        try:
            module = importlib.import_module(name)
            modules[name] = {"available": True, "version": str(getattr(module, "__version__", getattr(module, "VersionBind", "unknown")))}
        except Exception as exc:
            modules[name] = {"available": False, "reason": str(exc)}
    return {"python": sys.version.split()[0], "python_supported": sys.version_info >= (3, 10),
            "standard_library_tools": "DOCX text extraction, structural checks, report validation and DOCX generation",
            "modules": modules, "libreoffice": shutil.which("soffice") or shutil.which("libreoffice"),
            "requirements": {"pdf_geometry_and_render": "PyMuPDF (import pymupdf; old fitz fallback supported)",
                             "docx_generation": "Python standard library only",
                             "independent_docx_test": "python-docx, optional", "docx_page_render": "LibreOffice or host preview"}}


if __name__ == "__main__":
    configure_stdio()
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["python_supported"] else 1)
