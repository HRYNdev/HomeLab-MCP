"""Uptime Kuma MCP — мониторинг доступности сервисов.

Примечание: Uptime Kuma использует Socket.IO как основной протокол.
Этот сервер работает через публичный REST API статус-страниц (/api/status-page)
и неофициальный /metrics endpoint (Prometheus-совместимый, если включён в настройках).
Для полного управления рекомендуется включить публичную статус-страницу.
"""

import os
import json
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

UPTIME_KUMA_URL = os.getenv("UPTIME_KUMA_URL", "http://localhost:3001").rstrip("/")
UPTIME_KUMA_USER = os.getenv("UPTIME_KUMA_USER", "")
UPTIME_KUMA_PASSWORD = os.getenv("UPTIME_KUMA_PASSWORD", "")
# Slug публичной статус-страницы (Settings → Status Pages → slug)
UPTIME_KUMA_SLUG = os.getenv("UPTIME_KUMA_SLUG", "default")

mcp = FastMCP("uptime-kuma")


def _check() -> str | None:
    if not UPTIME_KUMA_URL:
        return "Error: UPTIME_KUMA_URL not set in .env"
    return None


async def _get_public(slug: str) -> dict:
    """Публичный API статус-страницы — работает без авторизации."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{UPTIME_KUMA_URL}/api/status-page/{slug}",
            timeout=10,
        )
        r.raise_for_status()
        return r.json()


async def _get_heartbeats(slug: str) -> dict:
    """Публичный API heartbeats для статус-страницы."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{UPTIME_KUMA_URL}/api/status-page/heartbeat/{slug}",
            timeout=10,
        )
        r.raise_for_status()
        return r.json()


async def _get_metrics() -> str:
    """Prometheus /metrics endpoint (нужно включить в Settings → Advanced → Enable Prometheus metrics)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{UPTIME_KUMA_URL}/metrics", timeout=10)
        r.raise_for_status()
        return r.text


def _parse_metrics(raw: str) -> list[dict]:
    """Парсим Prometheus metrics в список мониторов."""
    monitors = {}
    for line in raw.splitlines():
        if line.startswith("#"):
            continue
        # monitor_status{monitor_name="...",monitor_type="..."} 1
        m = re.match(r'monitor_status\{monitor_name="([^"]+)",monitor_type="([^"]+)".*\}\s+(\d+)', line)
        if m:
            name, mtype, status = m.group(1), m.group(2), int(m.group(3))
            monitors[name] = {"name": name, "type": mtype, "status": "up" if status == 1 else "down"}
        # monitor_response_time{monitor_name="..."} 123
        m2 = re.match(r'monitor_response_time\{monitor_name="([^"]+)".*\}\s+(\S+)', line)
        if m2:
            name, rt = m2.group(1), m2.group(2)
            if name in monitors:
                try:
                    monitors[name]["response_time_ms"] = float(rt)
                except ValueError:
                    pass
    return list(monitors.values())


@mcp.tool()
async def uptime_kuma_status() -> str:
    """
    Overview from the public status page: which monitors are up/down.

    Uses the public status page API — no authentication required.
    Make sure you have a status page created (Settings → Status Pages).
    """
    err = _check()
    if err:
        return err
    try:
        page_data = await _get_public(UPTIME_KUMA_SLUG)
        id_to_name = {}
        for group in page_data.get("publicGroupList", []):
            for m in group.get("monitorList", []):
                id_to_name[str(m["id"])] = m["name"]

        data = await _get_heartbeats(UPTIME_KUMA_SLUG)
        heartbeat_list = data.get("heartbeatList", {})
        uptime_list = data.get("uptimeList", {})

        monitors = []
        for monitor_id, beats in heartbeat_list.items():
            if not beats:
                continue
            latest = beats[-1]
            status = "up" if latest.get("status") == 1 else "down"
            uptime_24h = uptime_list.get(f"{monitor_id}_24", 0)
            monitors.append({
                "name": id_to_name.get(str(monitor_id), f"Monitor {monitor_id}"),
                "status": status,
                "ping_ms": latest.get("ping"),
                "uptime_24h_percent": round(uptime_24h * 100, 1),
                "last_check": str(latest.get("time", ""))[:19],
                "message": latest.get("msg", ""),
            })

        total = len(monitors)
        down = [m for m in monitors if m["status"] == "down"]

        return json.dumps({
            "summary": {
                "total": total,
                "up": total - len(down),
                "down": len(down),
                "overall": "all_good" if not down else "issues_detected",
            },
            "down_monitors": [m["name"] for m in down],
            "monitors": monitors,
        }, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return (
                f"Error: status page '{UPTIME_KUMA_SLUG}' not found. "
                "Create one in Uptime Kuma → Status Pages, then set UPTIME_KUMA_SLUG in .env"
            )
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def uptime_kuma_monitors_metrics() -> str:
    """
    Detailed monitor list with response times via Prometheus metrics endpoint.

    Requires: Settings → Advanced → Enable Prometheus metrics (toggle ON).
    """
    err = _check()
    if err:
        return err
    try:
        raw = await _get_metrics()
        monitors = _parse_metrics(raw)
        if not monitors:
            return (
                "No data from /metrics. Enable it: Settings → Advanced → Enable Prometheus metrics"
            )
        return json.dumps(monitors, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Prometheus metrics not enabled. Go to Settings → Advanced → Enable Prometheus metrics"
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def uptime_kuma_status_page_info() -> str:
    """
    Info about the configured public status page (title, description, monitors list).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get_public(UPTIME_KUMA_SLUG)
        config = data.get("config", {})
        monitors = data.get("publicGroupList", [])
        monitor_names = []
        for group in monitors:
            for m in group.get("monitorList", []):
                monitor_names.append(m.get("name"))
        return json.dumps({
            "title": config.get("title"),
            "description": config.get("description"),
            "slug": UPTIME_KUMA_SLUG,
            "public_url": f"{UPTIME_KUMA_URL}/status/{UPTIME_KUMA_SLUG}",
            "monitors_on_page": monitor_names,
        }, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return (
                f"Status page '{UPTIME_KUMA_SLUG}' not found. "
                "Create it in Uptime Kuma → Status Pages, set slug, then add UPTIME_KUMA_SLUG to .env"
            )
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def uptime_kuma_heartbeat_history(monitor_name: str) -> str:
    """
    Recent heartbeat history for a specific monitor from the status page.

    monitor_name: monitor name as shown in Uptime Kuma (case-sensitive)
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get_heartbeats(UPTIME_KUMA_SLUG)
        heartbeat_list = data.get("heartbeatList", {})

        page_data = await _get_public(UPTIME_KUMA_SLUG)
        id_to_name = {}
        for group in page_data.get("publicGroupList", []):
            for m in group.get("monitorList", []):
                id_to_name[str(m["id"])] = m["name"]

        for monitor_id, beats in heartbeat_list.items():
            if not beats:
                continue
            if id_to_name.get(str(monitor_id), "") == monitor_name:
                history = []
                for b in beats[-30:]:
                    history.append({
                        "time": str(b.get("time", ""))[:19],
                        "status": "up" if b.get("status") == 1 else "down",
                        "ping_ms": b.get("ping"),
                        "msg": b.get("msg", ""),
                    })
                return json.dumps(history, ensure_ascii=False, indent=2)

        return f"Monitor '{monitor_name}' not found on status page '{UPTIME_KUMA_SLUG}'"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
