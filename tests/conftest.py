import pytest
from ursina import Ursina

@pytest.fixture(scope="session")
def ursina_app():
    app = Ursina(headless=True)
    yield app