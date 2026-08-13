import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_neo4j_healthcheck import Neo4jHealthCheck, create_neo4j_health_router


class MockAsyncDriver:
    def __init__(self, should_succeed=True, delay=0.0):
        self.should_succeed = should_succeed
        self.delay = delay

    async def execute_query(self, query, database_=None):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if not self.should_succeed:
            raise RuntimeError("Database connection refused")
        return [({"ping": 1}, None, None)]


class MockSyncDriver:
    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed

    def execute_query(self, query, database_=None):
        if not self.should_succeed:
            raise ConnectionError("Neo4j node unreachable")
        return [({"ping": 1}, None, None)]


@pytest.mark.asyncio
async def test_async_driver_healthy():
    driver = MockAsyncDriver(should_succeed=True)
    checker = Neo4jHealthCheck(driver_provider=driver, database="neo4j")
    result = await checker.check_health()

    assert result["status"] == "healthy"
    assert result["database"] == "neo4j"
    assert result["details"]["connected"] is True
    assert result["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_async_driver_unhealthy():
    driver = MockAsyncDriver(should_succeed=False)
    checker = Neo4jHealthCheck(driver_provider=driver)
    result = await checker.check_health()

    assert result["status"] == "unhealthy"
    assert result["details"]["connected"] is False
    assert "Database connection refused" in result["details"]["error"]


@pytest.mark.asyncio
async def test_async_driver_timeout():
    driver = MockAsyncDriver(should_succeed=True, delay=0.5)
    checker = Neo4jHealthCheck(driver_provider=driver, timeout=0.1)
    result = await checker.check_health()

    assert result["status"] == "unhealthy"
    assert result["details"]["connected"] is False


@pytest.mark.asyncio
async def test_sync_driver_healthy():
    driver = MockSyncDriver(should_succeed=True)
    checker = Neo4jHealthCheck(driver_provider=driver)
    result = await checker.check_health()

    assert result["status"] == "healthy"
    assert result["details"]["connected"] is True


@pytest.mark.asyncio
async def test_sync_driver_unhealthy():
    driver = MockSyncDriver(should_succeed=False)
    checker = Neo4jHealthCheck(driver_provider=driver)
    result = await checker.check_health()

    assert result["status"] == "unhealthy"
    assert result["details"]["connected"] is False
    assert "Neo4j node unreachable" in result["details"]["error"]


@pytest.mark.asyncio
async def test_callable_driver_provider():
    driver = MockAsyncDriver(should_succeed=True)
    provider = lambda: driver
    checker = Neo4jHealthCheck(driver_provider=provider)
    result = await checker.check_health()

    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_router_integration_healthy():
    driver = MockAsyncDriver(should_succeed=True)
    app = FastAPI()
    router = create_neo4j_health_router(driver_provider=driver, prefix="/health")
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_router_integration_unhealthy():
    driver = MockAsyncDriver(should_succeed=False)
    app = FastAPI()
    router = create_neo4j_health_router(
        driver_provider=driver, prefix="/healthcheck", unhealthy_status_code=503
    )
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthcheck")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
