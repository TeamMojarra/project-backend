import sys
from pathlib import Path

from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "API Reservent funcionando correctamente"