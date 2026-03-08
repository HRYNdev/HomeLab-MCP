"""Portainer MCP — управление Docker контейнерами через Portainer API."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

PORTAINER_URL = os.getenv("PORTAINER_URL", "").rstrip("/")
PORTAINER_TOKEN = os.getenv("PORTAINER_TOKEN", "")
PORTAINER_USER = os.getenv("PORTAINER_USER", "admin")
PORTAINER_PASSWORD = os.getenv("PORTAINER_PASSWORD", "")
PORTAINER_VERIFY_SSL = os.getenv("PORTAINER_VERIFY_SSL", "false").lower() == "true"

mcp = FastMCP("portainer")


def _check() -> str | None:
    if not PORTAINER_URL:
        return "Error: PORTAINER_URL not set in .env"
    return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=PORTAINER_VERIFY_SSL, timeout=15)


async def _get_token(client: httpx.AsyncClient) -> str:
    """Получить JWT токен через логин (если нет API token)."""
    r = await client.post(
        f"{PORTAINER_URL}/api/auth",
        json={"username": PORTAINER_USER, "password": PORTAINER_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["jwt"]


def _auth_headers(token: str) -> dict:
    # Portainer API tokens use X-API-Key, JWT uses Authorization Bearer
    if token.startswith("ptr_"):
        return {"X-API-Key": token}
    return {"Authorization": f"Bearer {token}"}


async def _get(path: str, params: dict | None = None) -> dict | list:
    async with _client() as c:
        token = PORTAINER_TOKEN if PORTAINER_TOKEN else await _get_token(c)
        r = await c.get(
            f"{PORTAINER_URL}/api{path}",
            headers=_auth_headers(token),
            params=params or {},
        )
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict | list:
    async with _client() as c:
        token = PORTAINER_TOKEN if PORTAINER_TOKEN else await _get_token(c)
        r = await c.post(
            f"{PORTAINER_URL}/api{path}",
            headers=_auth_headers(token),
            json=data or {},
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code}


async def _get_endpoint_id() -> int:
    """Получить ID первого endpoint (обычно 1)."""
    endpoints = await _get("/endpoints")
    if isinstance(endpoints, list) and endpoints:
        return endpoints[0]["Id"]
    return 1


@mcp.tool()
async def portainer_endpoints() -> str:
    """
    List Portainer endpoints (Docker environments).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/endpoints")
        result = []
        for e in data:
            result.append({
                "id": e.get("Id"),
                "name": e.get("Name"),
                "type": e.get("Type"),
                "status": "online" if e.get("Status") == 1 else "offline",
                "url": e.get("URL", ""),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_containers(endpoint_id: int = 0, all: bool = True) -> str:
    """
    List Docker containers on a Portainer endpoint.

    endpoint_id: environment ID (0 = auto-detect first)
    all: include stopped containers (default True)
    """
    err = _check()
    if err:
        return err
    try:
        if not endpoint_id:
            endpoint_id = await _get_endpoint_id()
        params = {"all": 1 if all else 0}
        data = await _get(f"/endpoints/{endpoint_id}/docker/containers/json", params=params)
        result = []
        for c in data:
            names = [n.lstrip("/") for n in c.get("Names", [])]
            result.append({
                "id": c.get("Id", "")[:12],
                "name": names[0] if names else "",
                "image": c.get("Image", ""),
                "status": c.get("Status", ""),
                "state": c.get("State", ""),
                "ports": [
                    f"{p.get('IP', '')}:{p.get('PublicPort', '')}→{p.get('PrivatePort', '')}"
                    for p in c.get("Ports", []) if p.get("PublicPort")
                ],
            })
        return json.dumps({"count": len(result), "containers": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_container_action(endpoint_id: int, container_id: str, action: str) -> str:
    """
    Start, stop, restart or kill a Docker container.

    endpoint_id: environment ID
    container_id: container ID or name
    action: 'start', 'stop', 'restart', 'kill'
    """
    err = _check()
    if err:
        return err
    if action not in ("start", "stop", "restart", "kill"):
        return "Error: action must be one of: start, stop, restart, kill"
    try:
        await _post(f"/endpoints/{endpoint_id}/docker/containers/{container_id}/{action}")
        return f"✓ Container '{container_id}' {action} initiated"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_container_logs(endpoint_id: int, container_id: str, lines: int = 50) -> str:
    """
    Get logs from a Docker container.

    endpoint_id: environment ID
    container_id: container ID or name
    lines: number of last lines to return (default 50)
    """
    err = _check()
    if err:
        return err
    try:
        async with _client() as c:
            token = PORTAINER_TOKEN if PORTAINER_TOKEN else await _get_token(c)
            r = await c.get(
                f"{PORTAINER_URL}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/logs",
                headers=_auth_headers(token),
                params={"stdout": 1, "stderr": 1, "tail": lines},
            )
            r.raise_for_status()
            return r.text[-8000:] if len(r.text) > 8000 else r.text
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_stacks(endpoint_id: int = 0) -> str:
    """
    List Docker Compose stacks managed by Portainer.

    endpoint_id: environment ID (0 = auto-detect first)
    """
    err = _check()
    if err:
        return err
    try:
        if not endpoint_id:
            endpoint_id = await _get_endpoint_id()
        data = await _get("/stacks", params={"endpointId": endpoint_id})
        result = []
        for s in data:
            result.append({
                "id": s.get("Id"),
                "name": s.get("Name"),
                "status": "active" if s.get("Status") == 1 else "inactive",
                "type": s.get("Type"),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_stack_action(stack_id: int, action: str, endpoint_id: int = 0) -> str:
    """
    Start or stop a Docker Compose stack.

    stack_id: stack ID from portainer_stacks()
    action: 'start' or 'stop'
    endpoint_id: environment ID (0 = auto-detect first)
    """
    err = _check()
    if err:
        return err
    if action not in ("start", "stop"):
        return "Error: action must be 'start' or 'stop'"
    try:
        if not endpoint_id:
            endpoint_id = await _get_endpoint_id()
        await _post(f"/stacks/{stack_id}/{action}", {"endpointId": endpoint_id})
        return f"✓ Stack {stack_id} {action} initiated"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_images(endpoint_id: int = 0) -> str:
    """
    List Docker images on a Portainer endpoint.

    endpoint_id: environment ID (0 = auto-detect first)
    """
    err = _check()
    if err:
        return err
    try:
        if not endpoint_id:
            endpoint_id = await _get_endpoint_id()
        data = await _get(f"/endpoints/{endpoint_id}/docker/images/json")
        result = []
        for img in data:
            tags = img.get("RepoTags") or ["<none>"]
            result.append({
                "id": img.get("Id", "")[:19],
                "tags": tags,
                "size_mb": round(img.get("Size", 0) / 1024**2, 1),
                "created": img.get("Created"),
            })
        return json.dumps({"count": len(result), "images": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def portainer_volumes(endpoint_id: int = 0) -> str:
    """
    List Docker volumes on a Portainer endpoint.

    endpoint_id: environment ID (0 = auto-detect first)
    """
    err = _check()
    if err:
        return err
    try:
        if not endpoint_id:
            endpoint_id = await _get_endpoint_id()
        data = await _get(f"/endpoints/{endpoint_id}/docker/volumes")
        volumes = data.get("Volumes") or []
        result = []
        for v in volumes:
            result.append({
                "name": v.get("Name"),
                "driver": v.get("Driver"),
                "mountpoint": v.get("Mountpoint", ""),
            })
        return json.dumps({"count": len(result), "volumes": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
