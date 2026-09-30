"""The running interpreter's lexical installation is not mutable Hermes state."""
from pathlib import Path
import sys
import os

from tests.home_io_guard import HomeIOGuard


def test_running_interpreter_alias_metadata_is_allowed():
    guard = HomeIOGuard(lambda: ((Path.home() / ".hermes").resolve(),))
    if os.path.islink(sys.executable):
        target = os.readlink(sys.executable)
        guard.check(target, metadata=True)
    guard.check(sys.executable, metadata=True)
