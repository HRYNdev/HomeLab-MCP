"""Proxmox VE MCP — управление виртуальными машинами и контейнерами."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

PROXMOX_HOST = os.getenv("PROXMOX_HOST", "")
PROXMOX_PORT = os.getenv("PROXMOX_PORT", "8006")
PROXMOX_USER = os.getenv("PROXMOX_USER", "root@pam")
PROXMOX_PASSWORD = os.getenv("PROXMOX_PASSWORD", "")
PROXMOX_TOKEN_ID = os.getenv("PROXMOX_TOKEN_ID", "")      # user@realm!tokenname
PROXMOX_TOKEN_SECRET = os.getenv("PROXMOX_TOKEN_SECRET", "")
PROXMOX_VERIFY_SSL = os.getenv("PROXMOX_VERIFY_SSL", "false").lower() == "true"

BASE_URL = f"https://{PROXMOX_HOST}:{PROXMOX_PORT}/api2/json"

mcp = FastMCP("proxmox")


def _check() -> str | None:
    if not PROXMOX_HOST:
        return "Error: PROXMOX_HOST not set in .env"
    if not PROXMOX_TOKEN_ID and not PROXMOX_PASSWORD:
        return "Error: set PROXMOX_TOKEN_ID+PROXMOX_TOKEN_SECRET or PROXMOX_PASSWORD in .env"
    return None


def _headers() -> dict:
    if PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET:
        return {"Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"}
    return {}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=PROXMOX_VERIFY_SSL, timeout=15)


async def _get_ticket() -> tuple[str, str]:
    """Получить ticket+CSRFPreventionToken через логин (если нет API token)."""
    async with _client() as c:
        r = await c.post(f"{BASE_URL}/access/ticket", data={
            "username": PROXMOX_USER,
            "password": PROXMOX_PASSWORD,
        })
        r.raise_for_status()
        d = r.json()["data"]
        return d["ticket"], d["CSRFPreventionToken"]


async def _get(path: str, params: dict | None = None) -> dict | list:
    if PROXMOX_TOKEN_ID:
        async with _client() as c:
            r = await c.get(f"{BASE_URL}{path}", headers=_headers(), params=params or {})
            r.raise_for_status()
            return r.json().get("data", r.json())
    else:
        ticket, _ = await _get_ticket()
        async with _client() as c:
            r = await c.get(f"{BASE_URL}{path}", cookies={"PVEAuthCookie": ticket}, params=params or {})
            r.raise_for_status()
            return r.json().get("data", r.json())


async def _post(path: str, data: dict | None = None) -> dict:
    if PROXMOX_TOKEN_ID:
        async with _client() as c:
            r = await c.post(f"{BASE_URL}{path}", headers=_headers(), data=data or {})
            r.raise_for_status()
            return r.json().get("data", r.json())
    else:
        ticket, csrf = await _get_ticket()
        async with _client() as c:
            r = await c.post(
                f"{BASE_URL}{path}",
                cookies={"PVEAuthCookie": ticket},
                headers={"CSRFPreventionToken": csrf},
                data=data or {},
            )
            r.raise_for_status()
            return r.json().get("data", r.json())


@mcp.tool()
async def proxmox_nodes() -> str:
    """
    List all Proxmox cluster nodes with status, CPU, memory and uptime.
    """
    err = _check()
    if err:
        return err
    try:
        nodes = await _get("/nodes")
        result = []
        for n in nodes:
            result.append({
                "node": n.get("node"),
                "status": n.get("status"),
                "cpu": round(n.get("cpu", 0) * 100, 1),
                "mem_used_gb": round(n.get("mem", 0) / 1024**3, 1),
                "mem_total_gb": round(n.get("maxmem", 0) / 1024**3, 1),
                "uptime_hours": round(n.get("uptime", 0) / 3600, 1),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_vms(node: str = "") -> str:
    """
    List virtual machines (QEMU/KVM) on a node or all nodes.

    node: node name (empty = auto-detect first node)
    """
    err = _check()
    if err:
        return err
    try:
        if not node:
            nodes = await _get("/nodes")
            node = nodes[0]["node"] if nodes else "pve"
        vms = await _get(f"/nodes/{node}/qemu")
        result = []
        for vm in vms:
            result.append({
                "vmid": vm.get("vmid"),
                "name": vm.get("name"),
                "status": vm.get("status"),
                "cpu_usage": round(vm.get("cpu", 0) * 100, 1),
                "mem_mb": round(vm.get("mem", 0) / 1024**2, 0),
                "maxmem_mb": round(vm.get("maxmem", 0) / 1024**2, 0),
                "uptime_hours": round(vm.get("uptime", 0) / 3600, 1),
                "node": node,
            })
        return json.dumps(sorted(result, key=lambda x: x["vmid"]), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_containers(node: str = "") -> str:
    """
    List LXC containers on a node or all nodes.

    node: node name (empty = auto-detect first node)
    """
    err = _check()
    if err:
        return err
    try:
        if not node:
            nodes = await _get("/nodes")
            node = nodes[0]["node"] if nodes else "pve"
        cts = await _get(f"/nodes/{node}/lxc")
        result = []
        for ct in cts:
            result.append({
                "vmid": ct.get("vmid"),
                "name": ct.get("name"),
                "status": ct.get("status"),
                "cpu_usage": round(ct.get("cpu", 0) * 100, 1),
                "mem_mb": round(ct.get("mem", 0) / 1024**2, 0),
                "uptime_hours": round(ct.get("uptime", 0) / 3600, 1),
                "node": node,
            })
        return json.dumps(sorted(result, key=lambda x: x["vmid"]), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_vm_start(node: str, vmid: int) -> str:
    """
    Start a virtual machine.

    node: Proxmox node name, e.g. 'pve'
    vmid: VM ID, e.g. 100
    """
    err = _check()
    if err:
        return err
    try:
        task = await _post(f"/nodes/{node}/qemu/{vmid}/status/start")
        return f"✓ VM {vmid} start task: {task}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_vm_stop(node: str, vmid: int, force: bool = False) -> str:
    """
    Stop a virtual machine (graceful shutdown by default).

    node: Proxmox node name
    vmid: VM ID
    force: if True, force stop (like pulling power plug)
    """
    err = _check()
    if err:
        return err
    try:
        path = f"/nodes/{node}/qemu/{vmid}/status/{'stop' if force else 'shutdown'}"
        task = await _post(path)
        action = "force-stopped" if force else "shutdown"
        return f"✓ VM {vmid} {action}: {task}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_vm_reboot(node: str, vmid: int) -> str:
    """
    Reboot a virtual machine.

    node: Proxmox node name
    vmid: VM ID
    """
    err = _check()
    if err:
        return err
    try:
        task = await _post(f"/nodes/{node}/qemu/{vmid}/status/reboot")
        return f"✓ VM {vmid} rebooting: {task}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_container_start(node: str, vmid: int) -> str:
    """
    Start an LXC container.

    node: Proxmox node name
    vmid: container ID
    """
    err = _check()
    if err:
        return err
    try:
        task = await _post(f"/nodes/{node}/lxc/{vmid}/status/start")
        return f"✓ Container {vmid} start task: {task}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_container_stop(node: str, vmid: int) -> str:
    """
    Stop an LXC container.

    node: Proxmox node name
    vmid: container ID
    """
    err = _check()
    if err:
        return err
    try:
        task = await _post(f"/nodes/{node}/lxc/{vmid}/status/stop")
        return f"✓ Container {vmid} stopped: {task}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_node_status(node: str = "") -> str:
    """
    Detailed status of a Proxmox node: CPU, memory, disk, load.

    node: node name (empty = auto-detect first node)
    """
    err = _check()
    if err:
        return err
    try:
        if not node:
            nodes = await _get("/nodes")
            node = nodes[0]["node"] if nodes else "pve"
        data = await _get(f"/nodes/{node}/status")
        return json.dumps({
            "node": node,
            "cpu_usage_percent": round(data.get("cpu", 0) * 100, 1),
            "mem_used_gb": round(data.get("memory", {}).get("used", 0) / 1024**3, 2),
            "mem_total_gb": round(data.get("memory", {}).get("total", 0) / 1024**3, 2),
            "swap_used_gb": round(data.get("swap", {}).get("used", 0) / 1024**3, 2),
            "disk_used_gb": round(data.get("rootfs", {}).get("used", 0) / 1024**3, 2),
            "disk_total_gb": round(data.get("rootfs", {}).get("total", 0) / 1024**3, 2),
            "load_avg": data.get("loadavg"),
            "uptime_hours": round(data.get("uptime", 0) / 3600, 1),
            "kernel": data.get("kversion", ""),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_storage(node: str = "") -> str:
    """
    List storage pools on a Proxmox node with usage statistics.

    node: node name (empty = auto-detect first node)
    """
    err = _check()
    if err:
        return err
    try:
        if not node:
            nodes = await _get("/nodes")
            node = nodes[0]["node"] if nodes else "pve"
        storages = await _get(f"/nodes/{node}/storage")
        result = []
        for s in storages:
            result.append({
                "storage": s.get("storage"),
                "type": s.get("type"),
                "active": s.get("active"),
                "used_gb": round(s.get("used", 0) / 1024**3, 1),
                "total_gb": round(s.get("total", 0) / 1024**3, 1),
                "used_percent": round(s.get("used_fraction", 0) * 100, 1),
                "content": s.get("content", ""),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def proxmox_tasks(node: str = "", limit: int = 20) -> str:
    """
    Recent tasks on a Proxmox node (backups, migrations, snapshots, etc).

    node: node name (empty = auto-detect first node)
    limit: number of tasks to show (default 20)
    """
    err = _check()
    if err:
        return err
    try:
        if not node:
            nodes = await _get("/nodes")
            node = nodes[0]["node"] if nodes else "pve"
        tasks = await _get(f"/nodes/{node}/tasks", params={"limit": limit})
        result = []
        for t in tasks:
            result.append({
                "upid": t.get("upid", "")[-30:],
                "type": t.get("type"),
                "status": t.get("status"),
                "user": t.get("user"),
                "started": t.get("starttime"),
                "ended": t.get("endtime", "running"),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
