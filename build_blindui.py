#!/usr/bin/env python3
"""
Backwards-compatibility wrapper for build_maat.py (Maat, formerly BlindUI).
Zero external dependencies (Python 3 stdlib + sibling build_maat.py only).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from build_maat import (  # noqa: E402, F401
    MAX_BUNDLE_BYTES,
    MAX_KIT_BYTES,
    MAX_LINT_BYTES,
    MAX_TOKENS_BYTES,
    build_and_verify,
    main,
    minify_js,
    run_node_check,
    sync_exact_file,
    tokenize_js,
    validate_bundle_text,
    validate_css_tokens,
)

if __name__ == "__main__":
    sys.exit(main())
