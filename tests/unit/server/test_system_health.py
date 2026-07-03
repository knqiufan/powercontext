import json

import pytest


SENSITIVE_STARTUP_ERROR = (
    "failed to connect to postgresql://user:SYNTHETIC_SECRET@db.example/powermem "
    "from /synthetic/local/path"
)
SENSITIVE_FRAGMENTS = (
    "postgresql://user",
    "SYNTHETIC_SECRET",
    "db.example",
    "/synthetic/local/path",
)


def assert_sensitive_startup_error_hidden(body):
    response_text = json.dumps(body)
    for fragment in SENSITIVE_FRAGMENTS:
        assert fragment not in response_text


def build_app_with_startup_error():
    pytest.importorskip("fastapi", exc_type=ImportError)

    from fastapi import FastAPI

    app = FastAPI()
    app.state.service_ready = False
    app.state.storage_type = "sqlite"
    app.state.service_startup_error = SENSITIVE_STARTUP_ERROR
    app.state.storage_capabilities = None
    app.state.memory_service = None
    app.state.search_service = None
    app.state.user_service = None
    app.state.agent_service = None
    return app


def test_public_health_does_not_expose_startup_error():
    from fastapi.testclient import TestClient

    from server.api.v1.system import router

    app = build_app_with_startup_error()
    app.include_router(router, prefix="/api/v1")

    response = TestClient(app).get("/api/v1/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "degraded"
    assert body["data"]["memory_service_ready"] is False
    assert "startup_error" not in body["data"]

    assert_sensitive_startup_error_hidden(body)


def test_authenticated_status_does_not_expose_startup_error(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import system
    from server.api.v1.system import router
    from server.config import config

    async def empty_dependency_check():
        return {}

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")
    monkeypatch.setattr(system, "check_all_dependencies", empty_dependency_check)

    app = build_app_with_startup_error()
    app.include_router(router, prefix="/api/v1")

    response = TestClient(app).get(
        "/api/v1/system/status",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["memory_service_ready"] is False
    assert body["data"]["startup_error"]
    assert body["data"]["dependencies"]["memory_service"]["status"] == "unavailable"
    assert body["data"]["dependencies"]["memory_service"]["error_message"]
    assert_sensitive_startup_error_hidden(body)


def test_authenticated_status_does_not_expose_dependency_probe_error(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import system
    from server.api.v1.system import router
    from server.config import config
    from server.models.response import DependencyStatus

    async def dependency_check_with_raw_error():
        return {
            "database": DependencyStatus(
                name="database",
                status="unavailable",
                error_message=SENSITIVE_STARTUP_ERROR,
            )
        }

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")
    monkeypatch.setattr(system, "check_all_dependencies", dependency_check_with_raw_error)

    app = build_app_with_startup_error()
    app.state.service_startup_error = None
    app.state.service_ready = True
    app.include_router(router, prefix="/api/v1")

    response = TestClient(app).get(
        "/api/v1/system/status",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["dependencies"]["database"]["error_message"]
    assert_sensitive_startup_error_hidden(body)


def test_status_fallback_does_not_expose_startup_error(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import system
    from server.api.v1.system import router
    from server.config import config

    async def fail_dependency_check():
        raise RuntimeError(SENSITIVE_STARTUP_ERROR)

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")
    monkeypatch.setattr(system, "check_all_dependencies", fail_dependency_check)

    app = build_app_with_startup_error()
    app.include_router(router, prefix="/api/v1")

    response = TestClient(app).get(
        "/api/v1/system/status",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["memory_service_ready"] is False
    assert body["data"]["startup_error"]
    assert_sensitive_startup_error_hidden(body)


def test_service_unavailable_response_does_not_expose_startup_error(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import router
    from server.config import config
    from server.middleware.error_handler import error_handler
    from server.models.errors import APIError

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")

    app = build_app_with_startup_error()
    app.add_exception_handler(APIError, error_handler)
    app.include_router(router)

    response = TestClient(app).get(
        "/api/v1/users/user-1/profile",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["message"]
    assert_sensitive_startup_error_hidden(body)


def test_service_layer_error_response_does_not_expose_raw_exception(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import router
    from server.config import config
    from server.middleware.error_handler import error_handler
    from server.models.errors import APIError
    from server.services.user_service import UserService

    class FailingUserMemory:
        def profile(self, user_id):
            raise RuntimeError(SENSITIVE_STARTUP_ERROR)

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")

    service = UserService.__new__(UserService)
    service.user_memory = FailingUserMemory()

    app = build_app_with_startup_error()
    app.state.user_service = service
    app.add_exception_handler(APIError, error_handler)
    app.include_router(router)

    response = TestClient(app).get(
        "/api/v1/users/user-1/profile",
        headers={"X-API-Key": "secret"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["message"]
    assert_sensitive_startup_error_hidden(body)


def test_batch_response_data_does_not_expose_raw_exception(monkeypatch):
    from fastapi.testclient import TestClient

    from server.api.v1 import router
    from server.config import config
    from server.middleware.error_handler import error_handler
    from server.models.errors import APIError
    from server.services.memory_service import MemoryService

    class FailingMemory:
        def add(self, **kwargs):
            raise RuntimeError(SENSITIVE_STARTUP_ERROR)

    monkeypatch.setattr(config, "auth_enabled", True)
    monkeypatch.setattr(config, "api_keys", "secret")

    service = MemoryService.__new__(MemoryService)
    service.memory = FailingMemory()

    app = build_app_with_startup_error()
    app.state.memory_service = service
    app.add_exception_handler(APIError, error_handler)
    app.include_router(router)

    response = TestClient(app).post(
        "/api/v1/memories/batch",
        headers={"X-API-Key": "secret"},
        json={"memories": [{"content": "remember this"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["failed"][0]["error"]
    assert_sensitive_startup_error_hidden(body)
