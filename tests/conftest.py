"""pytest configuration — adds project paths to sys.path."""
import sys
import os

# Add each package to path so imports work without installation
for package in ["agents", "service", "persistence", "loadtest", "orchestrator"]:
    path = os.path.join(os.path.dirname(__file__), "..", package)
    if path not in sys.path:
        sys.path.insert(0, path)
