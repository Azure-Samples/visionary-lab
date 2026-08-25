"""Tests for the health, root, and public API surface."""

import json

from backend.api.endpoints.env import env_status
from backend.core.config import settings


def test_root_returns_welcome(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome" in data["message"]


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "image_jobs": {"store": "ok", "queue": "ok"},
    }


def test_openapi_schema_accessible(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "info" in schema


def test_openapi_schema_contains_no_video_api(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200

    serialized_schema = json.dumps(response.json()).lower()
    assert "video" not in serialized_schema
    assert "sora" not in serialized_schema

    for removed_path in (
        "/api/v1/videos",
        "/api/v1/videos/jobs",
        "/api/v1/gallery/videos",
    ):
        assert client.get(removed_path).status_code == 404


def test_env_status_accepts_local_storage_connection_string(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AZURE_STORAGE_CONNECTION_STRING",
        "UseDevelopmentStorage=true",
    )
    monkeypatch.setattr(settings, "AZURE_BLOB_SERVICE_URL", None)
    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_NAME", None)

    status = env_status()

    assert "AZURE_STORAGE_CONNECTION_STRING" in status["set"]
    assert "AZURE_BLOB_SERVICE_URL" not in status["missing"]
    assert "AZURE_STORAGE_ACCOUNT_NAME" not in status["missing"]


def test_sas_endpoint_returns_public_azurite_container(client, monkeypatch):
    monkeypatch.setattr(
        settings,
        "AZURE_STORAGE_CONNECTION_STRING",
        "UseDevelopmentStorage=true",
    )
    monkeypatch.setattr(settings, "AZURE_BLOB_SERVICE_URL", None)
    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_NAME", None)

    response = client.get("/api/v1/gallery/sas-tokens")

    assert response.status_code == 200
    payload = response.json()
    assert payload["image_sas_token"] == ""
    assert payload["image_container_url"] == (
        "http://127.0.0.1:10000/devstoreaccount1/images"
    )
