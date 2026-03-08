"""Grafana MCP — дашборды, алерты и метрики через Grafana HTTP API."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

GRAFANA_URL = os.getenv("GRAFANA_URL", "").rstrip("/")
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN", "")   # Service account token (рекомендуется)
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "")

mcp = FastMCP("grafana")


def _check() -> str | None:
    if not GRAFANA_URL:
        return "Error: GRAFANA_URL not set in .env"
    if not GRAFANA_TOKEN and not GRAFANA_PASSWORD:
        return "Error: set GRAFANA_TOKEN or GRAFANA_USER+GRAFANA_PASSWORD in .env"
    return None


def _client() -> httpx.AsyncClient:
    if GRAFANA_TOKEN:
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"},
            timeout=15,
        )
    return httpx.AsyncClient(
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
        timeout=15,
    )


async def _get(path: str, params: dict | None = None) -> dict | list:
    async with _client() as c:
        r = await c.get(f"{GRAFANA_URL}/api{path}", params=params or {})
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict:
    async with _client() as c:
        r = await c.post(f"{GRAFANA_URL}/api{path}", json=data or {})
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def grafana_status() -> str:
    """
    Grafana instance health, version and database status.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/health")
        return json.dumps({
            "version": data.get("version"),
            "commit": data.get("commit", ""),
            "database": data.get("database", ""),
            "db_health": data.get("db", ""),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_dashboards(query: str = "") -> str:
    """
    List Grafana dashboards, optionally filtered by name.

    query: search string (empty = all dashboards)
    """
    err = _check()
    if err:
        return err
    try:
        params = {"type": "dash-db", "limit": 100}
        if query:
            params["query"] = query
        data = await _get("/search", params)
        result = []
        for d in data:
            result.append({
                "id": d.get("id"),
                "uid": d.get("uid"),
                "title": d.get("title"),
                "folder": d.get("folderTitle", "General"),
                "url": d.get("url", ""),
                "tags": d.get("tags", []),
            })
        return json.dumps({"count": len(result), "dashboards": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_dashboard_detail(uid: str) -> str:
    """
    Get dashboard panels and metadata by UID.

    uid: dashboard UID from grafana_dashboards()
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get(f"/dashboards/uid/{uid}")
        dash = data.get("dashboard", {})
        meta = data.get("meta", {})
        panels = []
        for p in dash.get("panels", []):
            panels.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "type": p.get("type"),
            })
        return json.dumps({
            "title": dash.get("title"),
            "uid": dash.get("uid"),
            "tags": dash.get("tags", []),
            "created_by": meta.get("createdBy"),
            "updated_by": meta.get("updatedBy"),
            "panels": panels,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_alerts() -> str:
    """
    List Grafana alert rules with their current state.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/v1/provisioning/alert-rules")
        result = []
        for a in data:
            result.append({
                "uid": a.get("uid"),
                "title": a.get("title"),
                "folder": a.get("folderUID", ""),
                "condition": a.get("condition", ""),
                "for": a.get("for", ""),
            })
        return json.dumps({"count": len(result), "rules": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_alert_states() -> str:
    """
    Current firing/pending alert instances (active alerts). Supports Grafana 9+ unified alerting.
    """
    err = _check()
    if err:
        return err
    try:
        # Grafana 9+ unified alerting
        data = await _get("/alertmanager/grafana/api/v2/alerts")
        firing = []
        resolved = []
        for a in data:
            labels = a.get("labels", {})
            entry = {
                "name": labels.get("alertname", ""),
                "state": a.get("status", {}).get("state", ""),
                "severity": labels.get("severity", ""),
                "summary": a.get("annotations", {}).get("summary", ""),
                "starts_at": a.get("startsAt", ""),
            }
            if entry["state"] == "active":
                firing.append(entry)
            else:
                resolved.append(entry)
        return json.dumps({
            "firing_count": len(firing),
            "resolved_count": len(resolved),
            "firing": firing,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_datasources() -> str:
    """
    List configured data sources (Prometheus, InfluxDB, Loki, etc).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/datasources")
        result = []
        for ds in data:
            result.append({
                "id": ds.get("id"),
                "name": ds.get("name"),
                "type": ds.get("type"),
                "url": ds.get("url", ""),
                "default": ds.get("isDefault", False),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_organizations() -> str:
    """
    List Grafana organizations and current org info.
    """
    err = _check()
    if err:
        return err
    try:
        orgs = await _get("/orgs")
        current = await _get("/org")
        return json.dumps({
            "current": {"id": current.get("id"), "name": current.get("name")},
            "all": [{"id": o.get("id"), "name": o.get("name")} for o in orgs],
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def grafana_users() -> str:
    """
    List Grafana users.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/org/users")
        result = []
        for u in data:
            result.append({
                "login": u.get("login"),
                "name": u.get("name", ""),
                "email": u.get("email", ""),
                "role": u.get("role"),
                "last_seen": u.get("lastSeenAt", ""),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
