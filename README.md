# fastapi-neo4j-healthcheck 🚀

[![PyPI version](https://img.shields.io/pypi/v/fastapi-neo4j-healthcheck.svg)](https://pypi.org/project/fastapi-neo4j-healthcheck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-neo4j-healthcheck.svg)](https://pypi.org/project/fastapi-neo4j-healthcheck/)

Production-grade, zero-overhead Neo4j health check endpoint for [FastAPI](https://fastapi.tiangolo.com/) applications with Kubernetes liveness/readiness probe support.

## Features

- ⚡ **Sync & Async Driver Support**: Seamlessly works with `neo4j.AsyncGraphDatabase` and `neo4j.GraphDatabase`.
- 🩺 **Non-Blocking Ping**: Executes lightweight Cypher queries (`RETURN 1 AS ping`) off the main thread or via async I/O.
- ⏱️ **Timeout Protection**: Configurable timeout (default `3.0s`) to prevent health check hangs during database failover or high load.
- ⚓ **Kubernetes Ready**: Returns `200 OK` when healthy and `503 Service Unavailable` (customizable) when degraded.
- 📊 **Observability & Latency**: Includes latency in milliseconds (`latency_ms`) and database target details in the response payload.

## Installation

```bash
pip install fastapi-neo4j-healthcheck
```

Or with `neo4j` driver included:

```bash
pip install fastapi-neo4j-healthcheck[neo4j]
```

## Quickstart

### 1. Using Async Neo4j Driver (Recommended)

```python
from fastapi import FastAPI
from neo4j import AsyncGraphDatabase
from fastapi_neo4j_healthcheck import create_neo4j_health_router

app = FastAPI(title="Graph API")

# Initialize Neo4j Async Driver
driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

# Include Health Check Router
app.include_router(
    create_neo4j_health_router(
        driver_provider=driver,
        prefix="/health/neo4j",
        tags=["Health"],
    )
)
```

### 2. Using Sync Neo4j Driver

```python
from fastapi import FastAPI
from neo4j import GraphDatabase
from fastapi_neo4j_healthcheck import create_neo4j_health_router

app = FastAPI()
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

app.include_router(
    create_neo4j_health_router(driver_provider=driver, prefix="/healthcheck")
)
```

### 3. Dynamic / Dependency-Injected Driver Provider

```python
from fastapi import FastAPI
from fastapi_neo4j_healthcheck import create_neo4j_health_router

def get_db_driver():
    return current_app_state.neo4j_driver

app = FastAPI()
app.include_router(
    create_neo4j_health_router(driver_provider=get_db_driver)
)
```

## Response Schema

### Healthy (HTTP 200)

```json
{
  "status": "healthy",
  "database": "neo4j",
  "latency_ms": 3.45,
  "details": {
    "connected": true
  }
}
```

### Unhealthy (HTTP 503)

```json
{
  "status": "unhealthy",
  "database": "neo4j",
  "latency_ms": 3001.12,
  "details": {
    "connected": false,
    "error": "ServiceUnavailable: Could not perform discovery for database 'neo4j'"
  }
}
```

## Kubernetes Readiness Probe Configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/neo4j
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health/neo4j
    port: 8000
  initialDelaySeconds: 2
  periodSeconds: 5
```

## License

[MIT License](LICENSE) - Created by [Gabaoun](https://github.com/gabaoun).
