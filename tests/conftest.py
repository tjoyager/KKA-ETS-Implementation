from pathlib import Path
import pytest
from ursina import Ursina, application

@pytest.fixture(scope="session")
def ursina_app():
    app = Ursina(headless=True)
    application.asset_folder = Path(__file__).resolve().parent.parent
    application.fonts_folder = Path(__file__).resolve().parent.parent / "assets/fonts"
    yield app