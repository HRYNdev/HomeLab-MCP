"""AdGuard Home MCP — управление DNS и блокировкой рекламы."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

ADGUARD_URL = os.getenv("ADGUARD_URL", "http://192.168.1.1:3000").rstrip("/")
ADGUARD_USER = os.getenv("ADGUARD_USER", "admin")
ADGUARD_PASSWORD = os.getenv("ADGUARD_PASSWORD", "")

mcp = FastMCP("adguard")


def _check() -> str | None:
    if not ADGUARD_PASSWORD:
        return "Error: ADGUARD_PASSWORD not set in .env"
    return None


def _auth():
    return (ADGUARD_USER, ADGUARD_PASSWORD)


async def _get(path: str) -> dict | list:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ADGUARD_URL}/control/{path}", auth=_auth(), timeout=10)
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict | str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{ADGUARD_URL}/control/{path}",
            auth=_auth(),
            json=data,
            timeout=10,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return r.text


@mcp.tool()
async def adguard_status() -> str:
    """
    AdGuard Home status: DNS filtering state, version, uptime, stats summary.
    """
    err = _check()
    if err:
        return err
    try:
        status = await _get("status")
        stats = await _get("stats")
        return json.dumps({
            "protection_enabled": status.get("protection_enabled"),
            "dns_addresses": status.get("dns_addresses"),
            "version": status.get("version"),
            "queries_today": stats.get("num_dns_queries"),
            "blocked_today": stats.get("num_blocked_filtering"),
            "blocked_percent": round(
                stats.get("num_blocked_filtering", 0) / max(stats.get("num_dns_queries", 1), 1) * 100, 1
            ),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_toggle_protection(enable: bool) -> str:
    """
    Enable or disable AdGuard Home DNS filtering protection.

    enable: True to enable filtering, False to disable
    """
    err = _check()
    if err:
        return err
    try:
        await _post("dns_config", {"protection_enabled": enable})
        state = "enabled" if enable else "disabled"
        return f"✓ Protection {state}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_query_log(limit: int = 20) -> str:
    """
    Recent DNS query log: domains, clients, filtering results.

    limit: number of recent queries to show (default 20)
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get(f"querylog?limit={limit}&offset=0")
        entries = []
        for q in data.get("data", []):
            entry = {
                "time": q.get("time", "")[:19],
                "domain": q.get("question", {}).get("name", ""),
                "client": q.get("client", ""),
                "status": q.get("reason", ""),
                "blocked": q.get("reason", "") not in ("", "NotFilteredNotFound", "NotFilteredWhiteList"),
            }
            entries.append(entry)
        return json.dumps(entries, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_top_domains(blocked_only: bool = False) -> str:
    """
    Top queried or blocked domains statistics.

    blocked_only: if True, show only blocked domains
    """
    err = _check()
    if err:
        return err
    try:
        stats = await _get("stats")
        if blocked_only:
            domains = stats.get("top_blocked_domains", [])
        else:
            domains = stats.get("top_queried_domains", [])
        return json.dumps(domains[:20], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_top_clients() -> str:
    """
    Top DNS clients by number of requests.
    """
    err = _check()
    if err:
        return err
    try:
        stats = await _get("stats")
        return json.dumps(stats.get("top_clients", [])[:20], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_add_block(domain: str) -> str:
    """
    Add domain to custom blocklist (blocked for all clients).

    domain: domain to block, e.g. 'ads.example.com'
    """
    err = _check()
    if err:
        return err
    try:
        status = await _get("filtering/status")
        current = status.get("user_rules") or []
        rule = f"||{domain}^"
        if rule in current:
            return f"Already blocked: {domain}"
        current.append(rule)
        await _post("filtering/set_rules", {"rules": current})
        return f"Blocked: {domain}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_add_allow(domain: str) -> str:
    """
    Add domain to custom allowlist (whitelist — never blocked).

    domain: domain to whitelist, e.g. 'example.com'
    """
    err = _check()
    if err:
        return err
    try:
        status = await _get("filtering/status")
        current = status.get("user_rules") or []
        rule = f"@@||{domain}^"
        if rule in current:
            return f"Already whitelisted: {domain}"
        current.append(rule)
        await _post("filtering/set_rules", {"rules": current})
        return f"Whitelisted: {domain}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_list_filters() -> str:
    """
    List active AdGuard Home filter lists with rule counts and last update.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("filtering/status")
        filters = []
        for f in data.get("filters", []):
            filters.append({
                "name": f.get("name"),
                "url": f.get("url"),
                "enabled": f.get("enabled"),
                "rules_count": f.get("rules_count"),
                "last_updated": f.get("last_updated", "")[:10],
            })
        return json.dumps(filters, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_update_filters() -> str:
    """
    Force update all AdGuard Home filter lists.
    """
    err = _check()
    if err:
        return err
    try:
        await _post("filtering/refresh", {"whitelist": False})
        return "✓ Filter lists update triggered"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def adguard_clients() -> str:
    """
    List all known clients (devices) with their names and settings.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("clients")
        clients = []
        for c in (data.get("clients") or []):
            clients.append({
                "name": c.get("name"),
                "ids": c.get("ids", []),
                "filtering_enabled": c.get("filtering_enabled"),
                "safebrowsing_enabled": c.get("safebrowsing_enabled"),
                "use_global_settings": c.get("use_global_settings"),
            })
        for c in (data.get("auto_clients") or []):
            clients.append({
                "name": c.get("name"),
                "ip": c.get("ip"),
                "source": c.get("source"),
                "auto": True,
            })
        return json.dumps(clients, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
