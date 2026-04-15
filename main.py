"""web-tools v1.0.0 · Web Diagnostics Extension — entry point."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir in sys.path:
    sys.path.remove(_dir)
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in ("app", "handlers", "handlers_diag", "handlers_groups",
              "handlers_monitors", "handlers_scan", "skeleton", "panels", "panels_ui"):
        del sys.modules[_m]

from app import ext, chat    # noqa: F401
import handlers               # noqa: F401
import handlers_diag          # noqa: F401
import handlers_groups        # noqa: F401
import handlers_monitors      # noqa: F401
import handlers_scan          # noqa: F401
import skeleton               # noqa: F401
import panels_ui              # noqa: F401
import panels                 # noqa: F401
