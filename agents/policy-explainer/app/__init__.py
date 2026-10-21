"""Policy Explainer agent (A02) application package."""

from pathlib import Path
import sys


def _register_shared_package() -> None:
    """Make ``fi360_shared`` importable when this service runs from the repo or from Docker."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "shared"
        if (candidate / "fi360_shared" / "__init__.py").is_file():
            path = str(candidate)
            if path not in sys.path:
                sys.path.insert(0, path)
            return
    raise RuntimeError("shared/fi360_shared was not found above the policy-explainer package")


_register_shared_package()
