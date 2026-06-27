"""Tests que ejecutan los scripts de verificacion por fase."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "script",
    [
        "verify_phase1.py",
        "verify_phase2.py",
        "verify_phase3.py",
        "verify_phase4.py",
        "verify_phase5.py",
        "verify_phase6.py",
    ],
)
def test_verify_phase(script):
    """Ejecuta cada script de verificacion en un proceso aislado."""
    script_path = BASE_DIR / script
    assert script_path.exists(), f"{script} no existe"

    old_argv = sys.argv
    old_cwd = os.getcwd()
    try:
        os.chdir(BASE_DIR)
        sys.argv = [str(script_path)]
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
