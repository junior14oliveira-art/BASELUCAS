import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient

# Ensure apps/api directory is in sys.path
api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from src.main import app

@pytest.fixture
def client():
    """FastAPI TestClient fixture for web_ui endpoints."""
    with TestClient(app) as test_client:
        yield test_client
