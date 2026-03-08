"""Root conftest — ensures `src` is importable as a package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
