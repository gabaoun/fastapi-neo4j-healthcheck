import time
import inspect
import asyncio
from typing import Any, Callable, Dict, Optional, Union
from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse


class Neo4jHealthCheck:
    """
    Neo4j health check handler for FastAPI applications.
    Supports both sync and async Neo4j drivers.
    """

    def __init__(
        self,
        driver_provider: Union[Any, Callable[[], Any]],
        database: Optional[str] = None,
        timeout: float = 3.0,
        unhealthy_status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ):
        """
        Initialize the Neo4j health check handler.

        :param driver_provider: Neo4j Driver/AsyncDriver instance or a callable returning one.
        :param database: Target Neo4j database name (optional).
        :param timeout: Maximum seconds to wait for ping response (default: 3.0s).
        :param unhealthy_status_code: HTTP status code when database is unhealthy (default: 503).
        """
        self.driver_provider = driver_provider
        self.database = database
        self.timeout = timeout
        self.unhealthy_status_code = unhealthy_status_code

    def _get_driver(self) -> Any:
        if callable(self.driver_provider):
            return self.driver_provider()
        return self.driver_provider

    async def check_health(self) -> Dict[str, Any]:
        """
        Executes a lightweight Cypher query to verify Neo4j database connectivity and latency.
        """
        driver = self._get_driver()
        if not driver:
            return {
                "status": "unhealthy",
                "database": self.database or "default",
                "latency_ms": 0.0,
                "details": {"connected": False, "error": "No driver provided"},
            }

        start_time = time.perf_counter()
        try:
            # Check if async driver
            if hasattr(driver, "execute_query") and inspect.iscoroutinefunction(driver.execute_query):
                await asyncio.wait_for(
                    driver.execute_query("RETURN 1 AS ping", database_=self.database),
                    timeout=self.timeout,
                )
            elif hasattr(driver, "verify_connectivity") and inspect.iscoroutinefunction(driver.verify_connectivity):
                await asyncio.wait_for(
                    driver.verify_connectivity(auth=None),
                    timeout=self.timeout,
                )
            elif hasattr(driver, "execute_query"):
                # Sync driver run in executor to prevent blocking event loop
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: driver.execute_query("RETURN 1 AS ping", database_=self.database),
                    ),
                    timeout=self.timeout,
                )
            elif hasattr(driver, "verify_connectivity"):
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, driver.verify_connectivity),
                    timeout=self.timeout,
                )
            else:
                raise ValueError("Provided driver object does not match Neo4j driver interface.")

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "healthy",
                "database": self.database or "default",
                "latency_ms": latency_ms,
                "details": {"connected": True},
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "unhealthy",
                "database": self.database or "default",
                "latency_ms": latency_ms,
                "details": {"connected": False, "error": str(exc) or exc.__class__.__name__},
            }


def create_neo4j_health_router(
    driver_provider: Union[Any, Callable[[], Any]],
    prefix: str = "/healthcheck",
    tags: Optional[list] = None,
    database: Optional[str] = None,
    timeout: float = 3.0,
    unhealthy_status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
) -> APIRouter:
    """
    Creates a FastAPI APIRouter containing Neo4j health check endpoint.

    :param driver_provider: Neo4j Driver / AsyncDriver instance or callable getter.
    :param prefix: Endpoint path prefix (default: '/healthcheck').
    :param tags: OpenAPI documentation tags.
    :param database: Target database name.
    :param timeout: Maximum response timeout in seconds.
    :param unhealthy_status_code: HTTP status code when connection fails.
    :return: Configured FastAPI APIRouter.
    """
    router = APIRouter(tags=tags or ["Health"])
    checker = Neo4jHealthCheck(
        driver_provider=driver_provider,
        database=database,
        timeout=timeout,
        unhealthy_status_code=unhealthy_status_code,
    )

    @router.get(prefix)
    async def neo4j_health():
        result = await checker.check_health()
        status_code = (
            status.HTTP_200_OK
            if result["status"] == "healthy"
            else checker.unhealthy_status_code
        )
        return JSONResponse(content=result, status_code=status_code)

    return router
