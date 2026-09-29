import pytest
import function_app

@pytest.mark.asyncio
async def test_app_initializes():
    assert function_app.app is not None
