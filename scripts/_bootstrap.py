"""Make the project importable when a script is run directly.

``python scripts/chat.py`` puts ``scripts/`` on ``sys.path``, not the project
root, so ``import app`` fails with ModuleNotFoundError. Importing this module
first fixes that.

Every script here that touches ``app`` imports this before anything else. The
alternative — telling people to set PYTHONPATH, or to run everything as
``python -m`` — is a step that is easy to forget and produces an error message
that gives no hint about the cause.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
