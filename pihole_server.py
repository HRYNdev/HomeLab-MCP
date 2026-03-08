"""Pi-hole MCP — DNS-блокировщик рекламы. Поддерживает Pi-hole v6+."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

PIHOLE_URL = os.getenv("PIHOLE_URL", "http://pi.hole").rstrip("/")
PIHOLE_PASSWORD = os.getenv("PIHOLE_PASSWORD", "")

mcp = FastMCP("pihole")


def _check() -> str | None:
    if not PIHOLE_URL:
        return "Error: PIHOLE_URL not set in .env"
    return None


async def _get_sid(client: httpx.AsyncClient) -> str:
    """Получить session ID через авторизацию."""
    r = await client.post(
        f"{PIHOLE_URL}/api/auth",
        json={"password": PIHOLE_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    session = r.json().get("session", {})
    if not session.get("valid"):
        raise Exception(f"Auth failed: {session.get('message', 'invalid password')}")
    return session["sid"]


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        sid = await _get_sid(client)
        r = await client.get(
            f"{PIHOLE_URL}/api{path}",
            headers={"sid": sid},
            params=params or {},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        sid = await _get_sid(client)
        r = await client.post(
            f"{PIHOLE_URL}/api{path}",
            headers={"sid": sid},
            json=data or {},
            timeout=10,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code}


async def _delete(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        sid = await _get_sid(client)
        r = await client.delete(
            f"{PIHOLE_URL}/api{path}",
            headers={"sid": sid},
            timeout=10,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code}


@mcp.tool()
async def pihole_status() -> str:
    """
    Pi-hole status: blocking state, DNS queries today, blocked count and percentage.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/stats/summary")
        queries = data.get("queries", {})
        gravity = data.get("gravity", {})
        return json.dumps({
            "queries_today": queries.get("total"),
            "blocked_today": queries.get("blocked"),
            "blocked_percent": round(float(queries.get("percent_blocked", 0)), 1),
            "domains_blocked": gravity.get("domains_being_blocked"),
            "cached": queries.get("cached"),
            "forwarded": queries.get("forwarded"),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_blocking_state() -> str:
    """
    Check if Pi-hole blocking is currently enabled or disabled.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/dns/blocking")
        return json.dumps({
            "blocking": data.get("blocking"),
            "timer": data.get("timer"),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_enable() -> str:
    """
    Enable Pi-hole ad blocking.
    """
    err = _check()
    if err:
        return err
    try:
        await _post("/dns/blocking", {"blocking": True})
        return "✓ Pi-hole blocking enabled"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_disable(seconds: int = 0) -> str:
    """
    Disable Pi-hole ad blocking.

    seconds: how long to disable (0 = indefinitely)
    """
    err = _check()
    if err:
        return err
    try:
        body: dict = {"blocking": False}
        if seconds > 0:
            body["timer"] = seconds
        await _post("/dns/blocking", body)
        duration = f"for {seconds}s" if seconds else "indefinitely"
        return f"✓ Pi-hole blocking disabled {duration}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_top_blocked(limit: int = 10) -> str:
    """
    Top blocked domains.

    limit: number of domains to return (default 10)
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/stats/top_blocked", {"count": limit})
        domains = data.get("top_blocked", {})
        result = [{"domain": d, "hits": h} for d, h in domains.items()]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_query_log(limit: int = 20) -> str:
    """
    Recent DNS query log.

    limit: number of recent queries (default 20)
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/queries", {"max_results": limit})
        queries = data.get("queries", [])
        result = []
        for q in queries:
            result.append({
                "time": q.get("time"),
                "domain": q.get("domain"),
                "client": q.get("client", {}).get("ip"),
                "status": q.get("status"),
                "type": q.get("type"),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_blocklist() -> str:
    """
    List custom blocked domains (denylist).
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/domains/deny/exact")
        domains = data.get("domains", [])
        result = [{"domain": d.get("domain"), "comment": d.get("comment", "")} for d in domains]
        return json.dumps({"count": len(result), "domains": result}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_block_domain(domain: str, comment: str = "") -> str:
    """
    Add a domain to Pi-hole denylist (block it).

    domain: domain to block, e.g. 'ads.example.com'
    comment: optional comment
    """
    err = _check()
    if err:
        return err
    try:
        await _post("/domains/deny/exact", {"domain": domain, "comment": comment})
        return f"✓ Blocked: {domain}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def pihole_unblock_domain(domain: str) -> str:
    """
    Remove a domain from Pi-hole denylist (unblock it).

    domain: domain to unblock
    """
    err = _check()
    if err:
        return err
    try:
        await _delete(f"/domains/deny/exact/{domain}")
        return f"✓ Unblocked: {domain}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
