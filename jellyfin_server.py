"""Jellyfin MCP — управление медиасервером."""

import os
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "")

mcp = FastMCP("jellyfin")


def _check() -> str | None:
    if not JELLYFIN_API_KEY:
        return "Error: JELLYFIN_API_KEY not set in .env (Dashboard → API Keys → +)"
    return None


def _headers() -> dict:
    return {
        "X-Emby-Authorization": f'MediaBrowser Token="{JELLYFIN_API_KEY}"',
        "Content-Type": "application/json",
    }


async def _get(path: str, params: dict | None = None) -> dict | list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{JELLYFIN_URL}{path}",
            headers=_headers(),
            params=params or {},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict | None = None) -> dict | str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{JELLYFIN_URL}{path}",
            headers=_headers(),
            json=data or {},
            timeout=15,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return r.text


@mcp.tool()
async def jellyfin_server_info() -> str:
    """
    Jellyfin server info: version, OS, active sessions count.
    """
    err = _check()
    if err:
        return err
    try:
        info = await _get("/System/Info")
        sessions = await _get("/Sessions")
        return json.dumps({
            "server_name": info.get("ServerName"),
            "version": info.get("Version"),
            "os": info.get("OperatingSystem"),
            "local_address": info.get("LocalAddress"),
            "active_sessions": len(sessions) if isinstance(sessions, list) else 0,
            "startup_wizard_completed": info.get("StartupWizardCompleted"),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_libraries() -> str:
    """
    List Jellyfin media libraries with item counts.
    """
    err = _check()
    if err:
        return err
    try:
        data = await _get("/Library/VirtualFolders")
        result = []
        for lib in data:
            result.append({
                "name": lib.get("Name"),
                "type": lib.get("CollectionType", "mixed"),
                "locations": lib.get("Locations", []),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_active_sessions() -> str:
    """
    Currently active playback sessions (who is watching what).
    """
    err = _check()
    if err:
        return err
    try:
        sessions = await _get("/Sessions")
        result = []
        for s in sessions:
            np = s.get("NowPlayingItem")
            session = {
                "user": s.get("UserName", "Unknown"),
                "client": s.get("Client"),
                "device": s.get("DeviceName"),
                "playing": np.get("Name") if np else None,
                "media_type": np.get("Type") if np else None,
                "is_paused": s.get("PlayState", {}).get("IsPaused", False) if np else None,
            }
            result.append(session)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_search(query: str, media_type: str = "") -> str:
    """
    Search Jellyfin library for movies, series, or music.

    query: search term, e.g. 'Breaking Bad' or 'Pink Floyd'
    media_type: filter by type — 'Movie', 'Series', 'Audio', 'Album' (empty = all)
    """
    err = _check()
    if err:
        return err
    try:
        params = {"SearchTerm": query, "Limit": 20, "Recursive": "true"}
        if media_type:
            params["IncludeItemTypes"] = media_type
        data = await _get("/Items", params)
        items = []
        for item in data.get("Items", []):
            items.append({
                "id": item.get("Id"),
                "name": item.get("Name"),
                "type": item.get("Type"),
                "year": item.get("ProductionYear"),
                "rating": item.get("CommunityRating"),
                "overview": (item.get("Overview", "") or "")[:200],
            })
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_recent(limit: int = 10, media_type: str = "") -> str:
    """
    Recently added items to Jellyfin library.

    limit: number of items (default 10)
    media_type: 'Movie', 'Series', 'Audio' (empty = all)
    """
    err = _check()
    if err:
        return err
    try:
        params = {"Limit": limit, "Recursive": "true", "SortBy": "DateCreated", "SortOrder": "Descending"}
        if media_type:
            params["IncludeItemTypes"] = media_type
        data = await _get("/Items", params)
        items = []
        for item in data.get("Items", []):
            items.append({
                "name": item.get("Name"),
                "type": item.get("Type"),
                "year": item.get("ProductionYear"),
                "added": item.get("DateCreated", "")[:10],
            })
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_users() -> str:
    """
    List Jellyfin users with their admin status and last activity.
    """
    err = _check()
    if err:
        return err
    try:
        users = await _get("/Users")
        result = []
        for u in users:
            policy = u.get("Policy", {})
            result.append({
                "id": u.get("Id"),
                "name": u.get("Name"),
                "is_admin": policy.get("IsAdministrator", False),
                "is_disabled": policy.get("IsDisabled", False),
                "last_activity": u.get("LastActivityDate", "")[:10],
                "last_login": u.get("LastLoginDate", "")[:10],
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_library_stats() -> str:
    """
    Library statistics: total movies, series, episodes, songs.
    """
    err = _check()
    if err:
        return err
    try:
        results = {}
        for media_type in ["Movie", "Series", "Episode", "Audio"]:
            data = await _get("/Items", {
                "IncludeItemTypes": media_type,
                "Recursive": "true",
                "Limit": 1,
            })
            results[media_type.lower() + "s"] = data.get("TotalRecordCount", 0)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def jellyfin_scan_library() -> str:
    """
    Trigger Jellyfin library scan to find new media files.
    """
    err = _check()
    if err:
        return err
    try:
        await _post("/Library/Refresh")
        return "✓ Library scan started"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
