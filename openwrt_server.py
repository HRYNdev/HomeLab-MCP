"""MCP сервер для управления OpenWrt роутером через SSH."""

import os
from pathlib import Path

import asyncssh
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

OPENWRT_HOST = os.getenv("OPENWRT_HOST", "192.168.1.1")
OPENWRT_PORT = int(os.getenv("OPENWRT_PORT", "22"))
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
OPENWRT_PASSWORD = os.getenv("OPENWRT_PASSWORD", "")

# Только эти сервисы можно перезапускать через openwrt_service_restart
ALLOWED_RESTART = {"podkop", "vpn", "network", "firewall", "dnsmasq", "uhttpd", "wireless"}

mcp = FastMCP("openwrt")


def _conn_kwargs() -> dict:
    return {
        "host": OPENWRT_HOST,
        "port": OPENWRT_PORT,
        "username": OPENWRT_USER,
        "password": OPENWRT_PASSWORD,
        "known_hosts": None,
        "connect_timeout": 10,
    }


def _check_config() -> str | None:
    if not OPENWRT_PASSWORD:
        return "Ошибка: OPENWRT_PASSWORD не задан в .env"
    return None


async def _run(cmd: str) -> str:
    async with asyncssh.connect(**_conn_kwargs()) as conn:
        result = await conn.run(cmd)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.exit_status != 0 and not out:
            return f"Ошибка (exit {result.exit_status}): {err}"
        return out or err


# ── Мониторинг ────────────────────────────────────────────────────────────────

@mcp.tool()
async def openwrt_status() -> str:
    """
    Состояние роутера: uptime, загрузка CPU, память, версия OpenWrt.
    """
    err = _check_config()
    if err:
        return err
    try:
        cmd = (
            "echo '=UPTIME='; uptime; "
            "echo '=MEM='; free -m | awk 'NR==2{printf \"%s/%s MB (%.0f%%)\\n\", $3,$2,$3*100/$2}'; "
            "echo '=VERSION='; cat /etc/openwrt_release | grep DISTRIB_DESCRIPTION | cut -d'\"' -f2; "
            "echo '=LOAD='; cat /proc/loadavg"
        )
        raw = await _run(cmd)
        lines = raw.split("\n")
        result: dict[str, str] = {}
        key = None
        for line in lines:
            if line.startswith("=") and line.endswith("="):
                key = line.strip("=").lower()
            elif key and line:
                result[key] = line
                key = None
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_interfaces() -> str:
    """
    Статус сетевых интерфейсов роутера: IP-адреса, маршруты.
    """
    err = _check_config()
    if err:
        return err
    try:
        cmd = "echo '=ADDR='; ip -br addr; echo '=ROUTES='; ip route"
        raw = await _run(cmd)
        parts = raw.split("=ROUTES=")
        addr = parts[0].replace("=ADDR=", "").strip()
        routes = parts[1].strip() if len(parts) > 1 else ""
        import json
        return json.dumps({"interfaces": addr, "routes": routes}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_devices() -> str:
    """
    Устройства в сети: DHCP leases (имя, IP, MAC).
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run("cat /tmp/dhcp.leases 2>/dev/null || echo 'Нет DHCP leases'")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_logs(lines: int = 50) -> str:
    """
    Системный лог роутера (logread).

    lines: сколько последних строк показать (по умолчанию 50)
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"logread | tail -n {lines}")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_vpn_status() -> str:
    """
    Статус VPN / podkop: процессы, интерфейсы tun/tap/wg, конфиг podkop.
    """
    err = _check_config()
    if err:
        return err
    try:
        cmd = (
            "echo '=PODKOP='; /etc/init.d/podkop status 2>/dev/null || echo 'podkop не найден'; "
            "echo '=VPN_IFACES='; ip -br addr | grep -E 'tun[0-9]|tap[0-9]|wg[0-9]|ppp[0-9]|tailscale' || echo 'VPN интерфейсов нет'; "
            "echo '=WG='; wg show 2>/dev/null | grep -E 'interface|endpoint|latest' || echo 'no wg'; "
            "echo '=PROCESSES='; ps | grep -E 'sing-box|xray|v2ray|openvpn|tailscaled|wg-quick|xl2tpd|pptpd' | grep -v 'grep\\|ash -c' | awk '{print $1,$2,$NF}' || echo 'VPN процессов нет'"
        )
        raw = await _run(cmd)
        import json
        sections: dict[str, str] = {}
        key = None
        for line in raw.split("\n"):
            if line.startswith("=") and line.endswith("="):
                key = line.strip("=").lower()
                sections[key] = ""
            elif key is not None:
                sections[key] = (sections[key] + "\n" + line).strip()
        return json.dumps(sections, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_uci_get(key: str) -> str:
    """
    Прочитать UCI конфигурацию роутера (только чтение!).

    key: UCI путь, например 'network.wan' или 'firewall.@rule[0]'
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"uci show {key} 2>&1")
    except Exception as e:
        return f"Ошибка: {e}"


# ── Управление сервисами (whitelist) ──────────────────────────────────────────

@mcp.tool()
async def openwrt_service_restart(service: str) -> str:
    """
    Перезапустить сервис на роутере. Разрешены только: podkop, vpn, network, firewall, dnsmasq, uhttpd.

    service: имя сервиса из разрешённого списка
    """
    err = _check_config()
    if err:
        return err
    if service not in ALLOWED_RESTART:
        allowed = ", ".join(sorted(ALLOWED_RESTART))
        return f"Запрещено. Разрешённые сервисы: {allowed}"
    try:
        result = await _run(f"/etc/init.d/{service} restart 2>&1")
        return f"✓ Сервис {service} перезапущен: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_uci_set(commands: list[str]) -> str:
    """
    Записать UCI конфигурацию и применить. Принимает список команд без 'uci'.

    commands: например ["set wireless.@wifi-iface[0].key=mypassword", "commit wireless"]
    """
    err = _check_config()
    if err:
        return err
    try:
        script = " && ".join(f"uci {cmd}" for cmd in commands)
        return await _run(script)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def openwrt_run(cmd: str) -> str:
    """
    Выполнить произвольную команду на роутере через SSH.

    cmd: shell-команда, например 'wifi reload' или 'opkg install podkop'
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(cmd)
    except Exception as e:
        return f"Ошибка: {e}"


if __name__ == "__main__":
    mcp.run()
