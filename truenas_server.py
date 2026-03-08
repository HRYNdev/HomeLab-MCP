"""TrueNAS MCP — управление NAS через TrueNAS SCALE/CORE REST API."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

TRUENAS_URL = os.getenv("TRUENAS_URL", "").rstrip("/")
TRUENAS_API_KEY = os.getenv("TRUENAS_API_KEY", "")
TRUENAS_USER = os.getenv("TRUENAS_USER", "root")
TRUENAS_PASSWORD = os.getenv("TRUENAS_PASSWORD", "")
TRUENAS_VERIFY_SSL = os.getenv("TRUENAS_VERIFY_SSL", "false").lower() == "true"

BASE_URL = f"{TRUENAS_URL}/api/v2.0"

mcp = FastMCP("truenas")


def _check() -> str | None:
    if not TRUENAS_URL:
        return "Error: TRUENAS_URL not set in .env"
    if not TRUENAS_API_KEY and not TRUENAS_PASSWORD:
        return "Error: set TRUENAS_API_KEY or TRUENAS_USER+TRUENAS_PASSWORD in .env"
    return None


def _client() -> httpx.AsyncClient:
    if TRUENAS_API_KEY:
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {TRUENAS_API_KEY}"},
            verify=TRUENAS_VERIFY_SSL,
            timeout=20,
        )
    return httpx.AsyncClient(
        auth=(TRUENAS_USER, TRUENAS_PASSWORD),
        verify=TRUENAS_VERIFY_SSL,
        timeout=20,
    )


async def _get(path: str) -> dict | list:
    async with _client() as c:
        r = await c.get(f"{BASE_URL}{path}")
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict | list:
    async with _client() as c:
        r = await c.post(f"{BASE_URL}{path}", json=data)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code}


@mcp.tool()
async def truenas_system_info() -> str:
    """
    TrueNAS system info: hostname, version, uptime, CPU, memory.
    """
    err = _check()
    if err:
        return err
    try:
        info = await _get("/system/info")
        return json.dumps({
            "hostname": info.get("hostname"),
            "version": info.get("version"),
            "uptime": info.get("uptime"),
            "cpu_model": info.get("cpu_model", ""),
            "memory_gb": round(info.get("physmem", 0) / 1024**3, 1),
            "cores": info.get("cores", 0),
            "timezone": info.get("timezone", ""),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_pools() -> str:
    """
    List ZFS storage pools with status, size and health.
    """
    err = _check()
    if err:
        return err
    try:
        pools = await _get("/pool")
        result = []
        for p in pools:
            result.append({
                "name": p.get("name"),
                "status": p.get("status"),
                "healthy": p.get("healthy"),
                "size_gb": round(p.get("size", 0) / 1024**3, 1),
                "free_gb": round(p.get("free", 0) / 1024**3, 1),
                "allocated_gb": round(p.get("allocated", 0) / 1024**3, 1),
                "scrub_state": p.get("scan", {}).get("state", "") if p.get("scan") else "",
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_disks() -> str:
    """
    List physical disks with model, size, temperature and S.M.A.R.T. status.
    """
    err = _check()
    if err:
        return err
    try:
        disks = await _get("/disk")
        result = []
        for d in disks:
            result.append({
                "name": d.get("name"),
                "model": d.get("model", ""),
                "serial": d.get("serial", ""),
                "size_gb": round(d.get("size", 0) / 1024**3, 1),
                "temperature": d.get("temperature"),
                "rotationrate": d.get("rotationrate"),
                "type": d.get("type", ""),
            })
        return json.dumps({"count": len(result), "disks": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_datasets() -> str:
    """
    List ZFS datasets with usage statistics.
    """
    err = _check()
    if err:
        return err
    try:
        datasets = await _get("/pool/dataset")
        result = []
        for d in datasets:
            result.append({
                "name": d.get("name"),
                "type": d.get("type"),
                "used_gb": round(d.get("used", {}).get("parsed", 0) / 1024**3, 2),
                "available_gb": round(d.get("available", {}).get("parsed", 0) / 1024**3, 2),
                "compression": d.get("compression", {}).get("value", ""),
                "mountpoint": d.get("mountpoint"),
            })
        return json.dumps({"count": len(result), "datasets": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_snapshots(dataset: str = "") -> str:
    """
    List ZFS snapshots, optionally filtered by dataset.

    dataset: dataset name filter (empty = all snapshots, max 200)
    """
    err = _check()
    if err:
        return err
    try:
        path = "/zfs/snapshot"
        snapshots = await _get(path)
        if dataset:
            snapshots = [s for s in snapshots if s.get("dataset") == dataset]
        snapshots = snapshots[:200]
        result = []
        for s in snapshots:
            result.append({
                "name": s.get("name"),
                "dataset": s.get("dataset"),
                "created": s.get("properties", {}).get("creation", {}).get("value", ""),
                "used_mb": round(s.get("properties", {}).get("used", {}).get("parsed", 0) / 1024**2, 1),
            })
        return json.dumps({"count": len(result), "snapshots": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_services() -> str:
    """
    List TrueNAS services (SMB, NFS, SSH, etc) with running state.
    """
    err = _check()
    if err:
        return err
    try:
        services = await _get("/service")
        result = []
        for s in services:
            result.append({
                "service": s.get("service"),
                "state": s.get("state"),
                "enable": s.get("enable"),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_service_toggle(service: str, action: str) -> str:
    """
    Start or stop a TrueNAS service.

    service: service name, e.g. 'cifs', 'nfs', 'ssh', 'ftp'
    action: 'start' or 'stop'
    """
    err = _check()
    if err:
        return err
    if action not in ("start", "stop"):
        return "Error: action must be 'start' or 'stop'"
    try:
        await _post(f"/service/{action}", {"service": service})
        return f"✓ Service '{service}' {action} initiated"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_alerts() -> str:
    """
    List active TrueNAS system alerts.
    """
    err = _check()
    if err:
        return err
    try:
        alerts = await _get("/alert/list")
        result = []
        for a in alerts:
            dt = a.get("datetime", "")
            if isinstance(dt, dict):
                dt = dt.get("$date", "")
            result.append({
                "level": a.get("level"),
                "message": a.get("formatted", a.get("text", "")),
                "dismissed": a.get("dismissed", False),
                "datetime": str(dt),
            })
        critical = [r for r in result if r["level"] in ("CRITICAL", "ERROR") and not r["dismissed"]]
        warnings = [r for r in result if r["level"] == "WARNING" and not r["dismissed"]]
        return json.dumps({
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "critical": critical,
            "warnings": warnings,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_smart_results() -> str:
    """
    Latest S.M.A.R.T. test results for all disks.
    """
    err = _check()
    if err:
        return err
    try:
        results = await _get("/smart/test/results")
        result = []
        for r in results:
            result.append({
                "disk": r.get("disk"),
                "description": r.get("description", ""),
                "status": r.get("status"),
                "lifetime": r.get("lifetime", 0),
                "lba_of_first_error": r.get("lba_of_first_error"),
            })
        return json.dumps({"count": len(result), "results": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def truenas_replication_tasks() -> str:
    """
    List ZFS replication tasks with last run status.
    """
    err = _check()
    if err:
        return err
    try:
        tasks = await _get("/replication")
        result = []
        for t in tasks:
            result.append({
                "name": t.get("name"),
                "source": t.get("source_datasets", []),
                "target": t.get("target_dataset", ""),
                "enabled": t.get("enabled"),
                "state": t.get("state", {}).get("state", "") if isinstance(t.get("state"), dict) else str(t.get("state", "")),
                "last_run": str(t.get("state", {}).get("datetime", "") or "") if isinstance(t.get("state"), dict) else "",
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
