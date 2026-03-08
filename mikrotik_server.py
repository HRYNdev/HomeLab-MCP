"""MikroTik RouterOS MCP — управление роутером через REST API (RouterOS 7.1+)."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

MIKROTIK_HOST = os.getenv("MIKROTIK_HOST", "")
MIKROTIK_PORT = os.getenv("MIKROTIK_PORT", "443")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "admin")
MIKROTIK_PASSWORD = os.getenv("MIKROTIK_PASSWORD", "")
MIKROTIK_VERIFY_SSL = os.getenv("MIKROTIK_VERIFY_SSL", "false").lower() == "true"

BASE_URL = f"https://{MIKROTIK_HOST}:{MIKROTIK_PORT}/rest"

mcp = FastMCP("mikrotik")


def _check() -> str | None:
    if not MIKROTIK_HOST:
        return "Error: MIKROTIK_HOST not set in .env"
    return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        auth=(MIKROTIK_USER, MIKROTIK_PASSWORD),
        verify=MIKROTIK_VERIFY_SSL,
        timeout=15,
    )


async def _get(path: str, params: dict | None = None) -> list | dict:
    async with _client() as c:
        r = await c.get(f"{BASE_URL}{path}", params=params or {})
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict:
    async with _client() as c:
        r = await c.post(f"{BASE_URL}{path}", json=data or {})
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code}


@mcp.tool()
async def mikrotik_status() -> str:
    """
    MikroTik system status: CPU load, memory, uptime, model, RouterOS version.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/system/resource")
        total_mem = int(data.get("total-memory", 0))
        free_mem = int(data.get("free-memory", 0))
        used_mem = total_mem - free_mem
        return json.dumps({
            "board": data.get("board-name"),
            "version": data.get("version"),
            "cpu": data.get("cpu"),
            "cpu_load_percent": int(data.get("cpu-load", 0)),
            "mem_used_mb": round(used_mem / 1024**2, 1),
            "mem_total_mb": round(total_mem / 1024**2, 1),
            "uptime": data.get("uptime"),
            "architecture": data.get("architecture-name"),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_devices() -> str:
    """
    List devices connected via DHCP (leases) with IP, MAC, hostname and last seen.
    """
    err = _check()
    if err:
        return err
    try:
        leases = await _get("/ip/dhcp-server/lease")
        result = []
        for l in leases:
            if l.get("disabled") == "true":
                continue
            result.append({
                "hostname": l.get("host-name", l.get("comment", "")),
                "ip": l.get("active-address", l.get("address", "")),
                "mac": l.get("mac-address", ""),
                "last_seen": l.get("last-seen", ""),
                "expires": l.get("expires-after", ""),
                "dynamic": l.get("dynamic") == "true",
            })
        return json.dumps({"count": len(result), "devices": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_interfaces() -> str:
    """
    List network interfaces with status, type and IP addresses.
    """
    err = _check()
    if err:
        return err
    try:
        interfaces = await _get("/interface")
        addresses = await _get("/ip/address")

        addr_map: dict[str, list] = {}
        for a in addresses:
            iface = a.get("interface", "")
            if iface not in addr_map:
                addr_map[iface] = []
            addr_map[iface].append(a.get("address", ""))

        result = []
        for iface in interfaces:
            name = iface.get("name", "")
            result.append({
                "name": name,
                "type": iface.get("type", ""),
                "running": iface.get("running") == "true",
                "disabled": iface.get("disabled") == "true",
                "mtu": iface.get("mtu", ""),
                "comment": iface.get("comment", ""),
                "ip_addresses": addr_map.get(name, []),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_firewall_rules() -> str:
    """
    List firewall filter and NAT rules.
    """
    err = _check()
    if err:
        return err
    try:
        filters = await _get("/ip/firewall/filter")
        nat = await _get("/ip/firewall/nat")

        def fmt(rules: list) -> list:
            result = []
            for r in rules:
                result.append({
                    "chain": r.get("chain"),
                    "action": r.get("action"),
                    "comment": r.get("comment", ""),
                    "disabled": r.get("disabled") == "true",
                    "src": r.get("src-address", ""),
                    "dst": r.get("dst-address", ""),
                    "protocol": r.get("protocol", ""),
                    "dst_port": r.get("dst-port", ""),
                })
            return result

        return json.dumps({
            "filter_rules": fmt(filters),
            "nat_rules": fmt(nat),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_wireguard() -> str:
    """
    WireGuard interfaces and peers status.
    """
    err = _check()
    if err:
        return err
    try:
        interfaces = await _get("/interface/wireguard")
        peers = await _get("/interface/wireguard/peers")

        result = []
        for iface in interfaces:
            name = iface.get("name", "")
            iface_peers = [p for p in peers if p.get("interface") == name]
            result.append({
                "name": name,
                "disabled": iface.get("disabled") == "true",
                "mtu": iface.get("mtu", ""),
                "public_key": iface.get("public-key", ""),
                "peers": [{
                    "public_key": p.get("public-key", "")[:20] + "...",
                    "allowed_address": p.get("allowed-address", ""),
                    "endpoint": p.get("current-endpoint-address", ""),
                    "disabled": p.get("disabled") == "true",
                } for p in iface_peers],
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_identity() -> str:
    """
    MikroTik router identity (hostname).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/system/identity")
        return json.dumps({"identity": data.get("name")}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def mikrotik_reboot() -> str:
    """
    Reboot the MikroTik router.
    """
    err = _check()
    if err:
        return err
    try:
        await _post("/system/reboot")
        return "✓ Reboot command sent"
    except Exception as e:
        # Reboot disconnects immediately, so connection error is expected
        if "connect" in str(e).lower() or "timeout" in str(e).lower() or "reset" in str(e).lower():
            return "✓ Reboot command sent (connection closed as expected)"
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
