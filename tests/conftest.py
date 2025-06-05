import pytest
import asyncio

@pytest.fixture(scope="session")
def event_loop():
    """Cria um event loop para os testes assíncronos"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 