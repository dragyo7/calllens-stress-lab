"""Scaffold test to verify test harness and environment."""

import sys
import pytest


def test_python_version():
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_core_imports():
    import gnani
    import jiwer
    import numpy
    import scipy
    import soundfile
    import huggingface_hub
    import sqlalchemy
    import fastapi
    import uvicorn
    import dotenv
    import matplotlib
    import httpx
    import pydantic

    assert gnani is not None
    assert jiwer is not None
