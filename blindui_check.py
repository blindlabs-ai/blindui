#!/usr/bin/env python3
"""
Backwards-compatibility wrapper for maat_check.py (Maat, formerly BlindUI).
Preserves legacy BUI-01..BUI-11 rule prefixes alongside MAAT-12..MAAT-16.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import maat_check as _mc  # noqa: E402
from maat_check import (  # noqa: E402, F401
    JARGON_PATTERNS,
    _check_bui_11,
    _check_maat_12,
    _check_maat_13,
    _check_maat_14,
    _check_maat_15,
    extract_html_from_ui,
    extract_js_routes,
    extract_scripts,
    extract_server_routes,
    run_self_audit,
)


def check_app(
    ui_path: Path,
    server_path: Optional[Path] = None,
    surface: str = "app",
    html_var: Optional[str] = None,
    blindui_path: Optional[Path] = None,
    sso_server_path: Optional[Path] = None,
    rule_prefix: str = "BUI",
) -> Dict[str, Any]:
    return _mc.check_app(
        ui_path=ui_path,
        server_path=server_path,
        surface=surface,
        html_var=html_var,
        blindui_path=blindui_path,
        sso_server_path=sso_server_path,
        rule_prefix=rule_prefix,
    )


def main(argv: Optional[List[str]] = None) -> int:
    return _mc.main(argv=argv, default_rule_prefix="BUI")


if __name__ == "__main__":
    sys.exit(main())
