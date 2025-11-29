#!/usr/bin/env -S uv run --quiet --script
# /// script
# dependencies = [
#   "pytest",
#   "pytest-asyncio",
#   "pytest-cov",
#   "pydantic",
#   "structlog"
# ]
# ///
"""
Standalone test runner for schema tests
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now run pytest
import pytest

if __name__ == "__main__":
    # Run tests in this directory
    exit_code = pytest.main([
        str(Path(__file__).parent),
        "-v",
        "--tb=short"
    ])
    sys.exit(exit_code)
