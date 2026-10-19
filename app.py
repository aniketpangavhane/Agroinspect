"""Compatibility entry point for the new typed API.

The old Flask page used stale pickles and a different four-column schema. The
application now serves a same-origin prototype form and the validated,
versioned API. Train a model before using the form.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from crop_advisor.api import app  # noqa: E402  (path is configured just above)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
