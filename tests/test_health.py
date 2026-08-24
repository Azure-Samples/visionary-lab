"""Tests for the health, root, and public API surface."""

import json


def test_root_returns_welcome(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome" in data["message"]


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
