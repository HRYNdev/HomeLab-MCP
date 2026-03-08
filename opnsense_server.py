"""OPNsense MCP — управление роутером через REST API."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

OPNSENSE_HOST = os.getenv("OPNSENSE_HOST", "")
OPNSENSE_PORT = os.getenv("OPNSENSE_PORT", "443")
OPNSENSE_KEY = os.getenv("OPNSENSE_KEY", "")        # API Key
OPNSENSE_SECRET = os.getenv("OPNSENSE_SECRET", "")  # API Secret
OPNSENSE_VERIFY_SSL = os.getenv("OPNSENSE_VERIFY_SSL", "false").lower() == "true"

BASE_URL = f"https://{OPNSENSE_HOST}:{OPNSENSE_PORT}/api"

mcp = FastMCP("opnsense")


def _check() -> str | None:
    if not OPNSENSE_HOST:
        return "Error: OPNSENSE_HOST not set in .env"
    if not OPNSENSE_KEY or not OPNSENSE_SECRET:
        return "Error: OPNSENSE_KEY and OPNSENSE_SECRET not set in .env (System → Access → Users → API keys)"
    return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        auth=(OPNSENSE_KEY, OPNSENSE_SECRET),
        verify=OPNSENSE_VERIFY_SSL,
        timeout=15,
    )


async def _get(path: str) -> dict:
    async with _client() as c:
        r = await c.get(f"{BASE_URL}{path}")
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
async def opnsense_status() -> str:
    """
    OPNsense system status: CPU, memory, uptime, version, firmware.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/core/firmware/status")
        return json.dumps({
            "version": data.get("product_version"),
            "uptime": data.get("uptime"),
            "last_check": data.get("last_check"),
            "needs_reboot": data.get("upgrade_needs_reboot", False),
            "updates_available": len(data.get("updates", [])) > 0,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_interfaces() -> str:
    """
    Network interfaces status with IP addresses, gateway and link state.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/core/interfaces")
        result = []
        for iface_id, iface in data.items():
            result.append({
                "id": iface_id,
                "name": iface.get("name", iface_id),
                "device": iface.get("device", ""),
                "ip": iface.get("ipaddr", ""),
                "subnet": iface.get("subnet", ""),
                "status": iface.get("status", ""),
                "mac": iface.get("hwaddr", ""),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_arp() -> str:
    """
    ARP table — currently connected devices with IP and MAC addresses.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/diagnostics/interface/getArp")
        result = []
        for entry in data:
            result.append({
                "ip": entry.get("ip"),
                "mac": entry.get("mac"),
                "hostname": entry.get("hostname", ""),
                "interface": entry.get("intf", ""),
                "expired": entry.get("expired", False),
            })
        return json.dumps({"count": len(result), "devices": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_services() -> str:
    """
    List OPNsense services with their running status.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _post("/core/service/search", {"current": 1, "rowCount": 100})
        rows = data.get("rows", [])
        result = []
        for s in rows:
            result.append({
                "name": s.get("name"),
                "description": s.get("description", ""),
                "running": s.get("running") == 1 or s.get("running") is True,
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_service_restart(service_name: str) -> str:
    """
    Restart an OPNsense service.

    service_name: service name as shown in opnsense_services(), e.g. 'unbound', 'firewall'
    """
    err = _check()
    if err:
        return err
    try:
        await _post(f"/core/service/restart/{service_name}")
        return f"✓ Service '{service_name}' restart initiated"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_firewall_rules() -> str:
    """
    List firewall rules (aliases and filter rules summary).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _post("/firewall/filter/searchRule", {"current": 1, "rowCount": 100})
        rows = data.get("rows", [])
        result = []
        for r in rows:
            result.append({
                "description": r.get("description", ""),
                "action": r.get("type", ""),
                "interface": r.get("interface", ""),
                "protocol": r.get("protocol", "any"),
                "source": r.get("source_net", "any"),
                "destination": r.get("destination_net", "any"),
                "enabled": r.get("enabled") == "1",
            })
        return json.dumps({"count": len(result), "rules": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_vpn_openvpn() -> str:
    """
    OpenVPN instances and connected clients status.
    """
    err = _check()
    if err:
        return err
    try:
        status = await _get("/core/openvpn/status")
        return json.dumps({
            "sessions": status if isinstance(status, list) else status.get("rows", []),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_dhcp_leases() -> str:
    """
    DHCP leases — assigned IP addresses with MAC and hostname.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _post("/dhcpv4/leases/searchLease", {"current": 1, "rowCount": 500})
        rows = data.get("rows", [])
        result = []
        for l in rows:
            result.append({
                "ip": l.get("address", ""),
                "mac": l.get("mac", ""),
                "hostname": l.get("hostname", ""),
                "interface": l.get("if", ""),
                "expires": l.get("ends", ""),
                "state": l.get("binding", ""),
            })
        return json.dumps({"count": len(result), "leases": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def opnsense_reboot() -> str:
    """
    Reboot the OPNsense router.
    """
    err = _check()
    if err:
        return err
    try:
        await _post("/core/system/reboot")
        return "✓ Reboot command sent"
    except Exception as e:
        if "connect" in str(e).lower() or "timeout" in str(e).lower():
            return "✓ Reboot command sent (connection closed as expected)"
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
