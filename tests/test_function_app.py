import pytest
import function_app

def test_app_initializes():
    assert function_app.app is not None
