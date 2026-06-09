"""web-tools v1.5.0 · Web Diagnostics Extension — entry point (SDK 5.2.0 / SDL)."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir in sys.path:
    sys.path.remove(_dir)
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in ("app", "schemas_sdl", "schemas_sdl_builders",
              "handlers", "handlers_diag", "handlers_groups",
              "handlers_profiles", "handlers_monitors", "handlers_scan",
              "handlers_ui", "handlers_quick", "handlers_bulk", "handlers_audit",
              "handlers_schedule",
              "skeleton", "panels_ui", "panels_ui_base", "panels_ui_items",
              "panels_left", "panels_overview", "panels_detail", "panels_setup",
              "panels"):
        del sys.modules[_m]

from app import ext, chat    # noqa: F401

# SDL entity classes must be importable before any handler that uses them.
import schemas_sdl            # noqa: F401
import schemas_sdl_builders   # noqa: F401

import handlers               # noqa: F401
import handlers_diag          # noqa: F401
import handlers_groups        # noqa: F401
import handlers_profiles      # noqa: F401
import handlers_monitors      # noqa: F401
import handlers_scan          # noqa: F401
import handlers_ui             # noqa: F401
import handlers_quick          # noqa: F401
import handlers_bulk           # noqa: F401
import handlers_audit          # noqa: F401
import handlers_schedule      # noqa: F401
import skeleton               # noqa: F401
import panels_ui              # noqa: F401
import panels_setup           # noqa: F401
import panels                 # noqa: F401
