"""
MCP сервер для Home Assistant.
Позволяет Claude управлять умным домом: свет, климат, пылесос.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Загрузка .env из корня проекта MCP_SERVERS
load_dotenv(Path(__file__).parent / ".env")

HA_URL = os.getenv("HA_URL", "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN", "")

mcp = FastMCP("homeassistant")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


async def _get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{HA_URL}/api{path}", headers=_headers())
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict) -> Any:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{HA_URL}/api{path}", headers=_headers(), json=data)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def get_entity_state(entity_id: str) -> str:
    """
    Получить текущее состояние сущности Home Assistant.
    Например: switch.vykliuchatel_switch_2, vacuum.xiaomi_c102gl_e10e_robot_cleaner
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        state = await _get(f"/states/{entity_id}")
        result = {
            "entity_id": state["entity_id"],
            "state": state["state"],
            "attributes": state.get("attributes", {}),
            "last_changed": state.get("last_changed", ""),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def list_entities(domain: str = "") -> str:
    """
    Список всех сущностей Home Assistant.
    Параметр domain (опционально): light, switch, climate, vacuum, sensor, binary_sensor и т.д.
    Без параметра — все сущности.
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        states = await _get("/states")
        if domain:
            states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]
        result = [
            {
                "entity_id": s["entity_id"],
                "state": s["state"],
                "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
            }
            for s in states
        ]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def turn_on(entity_id: str) -> str:
    """
    Включить устройство (свет, выключатель и т.д.).
    entity_id: например switch.vykliuchatel_switch_2 или light.some_light
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        domain = entity_id.split(".")[0]
        await _post(f"/services/{domain}/turn_on", {"entity_id": entity_id})
        return f"✓ {entity_id} включён"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def turn_off(entity_id: str) -> str:
    """
    Выключить устройство (свет, выключатель и т.д.).
    entity_id: например switch.vykliuchatel_switch_2
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        domain = entity_id.split(".")[0]
        await _post(f"/services/{domain}/turn_off", {"entity_id": entity_id})
        return f"✓ {entity_id} выключен"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def toggle(entity_id: str) -> str:
    """
    Переключить состояние устройства (вкл↔выкл).
    entity_id: например switch.podsvetka_socket_1
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        domain = entity_id.split(".")[0]
        await _post(f"/services/{domain}/toggle", {"entity_id": entity_id})
        return f"✓ {entity_id} переключён"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def call_service(domain: str, service: str, entity_id: str = "", service_data: str = "{}") -> str:
    """
    Вызвать произвольный сервис Home Assistant.
    domain: light, switch, climate, vacuum, automation и т.д.
    service: turn_on, turn_off, start, pause, return_to_base и т.д.
    entity_id: ID сущности (опционально)
    service_data: JSON строка с дополнительными параметрами (опционально)
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        data: dict[str, Any] = json.loads(service_data)
        if entity_id:
            data["entity_id"] = entity_id
        result = await _post(f"/services/{domain}/{service}", data)
        return f"✓ {domain}.{service} выполнен\n{json.dumps(result, ensure_ascii=False, indent=2)}"
    except json.JSONDecodeError:
        return "Ошибка: service_data должна быть валидным JSON"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def get_temperature(room: str = "") -> str:
    """
    Получить показания температурных сенсоров.
    room: название комнаты для фильтрации (опционально).
    Без параметра — все температурные сенсоры.
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        states = await _get("/states")
        sensors = [
            s for s in states
            if s["entity_id"].startswith("sensor.")
            and s.get("attributes", {}).get("device_class") == "temperature"
        ]
        if room:
            room_lower = room.lower()
            sensors = [
                s for s in sensors
                if room_lower in s["entity_id"].lower()
                or room_lower in s.get("attributes", {}).get("friendly_name", "").lower()
            ]
        result = [
            {
                "entity_id": s["entity_id"],
                "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                "temperature": s["state"],
                "unit": s.get("attributes", {}).get("unit_of_measurement", "°C"),
            }
            for s in sensors
        ]
        if not result:
            return "Температурные сенсоры не найдены"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def vacuum_action(action: str, entity_id: str = "vacuum.xiaomi_c102gl_e10e_robot_cleaner") -> str:
    """
    Управление пылесосом Xiaomi.
    action: start | pause | stop | return_to_base | locate
    entity_id: ID пылесоса (по умолчанию vacuum.xiaomi_c102gl_e10e_robot_cleaner)
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"

    valid_actions = {"start", "pause", "stop", "return_to_base", "locate"}
    if action not in valid_actions:
        return f"Неверный action. Допустимые значения: {', '.join(valid_actions)}"

    try:
        await _post(f"/services/vacuum/{action}", {"entity_id": entity_id})
        action_names = {
            "start": "запущен",
            "pause": "на паузе",
            "stop": "остановлен",
            "return_to_base": "возвращается на базу",
            "locate": "сигналит (найди меня)",
        }
        return f"✓ Пылесос {action_names.get(action, action)}"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


async def _ws_lovelace(msg: dict) -> dict:
    """Отправить сообщение через HA WebSocket API и вернуть результат."""
    ws_url = HA_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        # Получаем приветствие
        await ws.recv()
        # Аутентификация
        await ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
        auth_result = json.loads(await ws.recv())
        if auth_result.get("type") != "auth_ok":
            raise Exception(f"WS auth failed: {auth_result}")
        # Отправляем команду
        msg["id"] = 1
        await ws.send(json.dumps(msg))
        result = json.loads(await ws.recv())
        return result


@mcp.tool()
async def list_lovelace_dashboards() -> str:
    """
    Список всех дашбордов Home Assistant с их url_path и режимом.
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        result = await _ws_lovelace({"type": "lovelace/dashboards/list"})
        if not result.get("success"):
            return f"Ошибка WS: {result}"
        return json.dumps(result["result"], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def get_lovelace_config(dashboard: str = "") -> str:
    """
    Получить конфигурацию дашборда Home Assistant (Lovelace).
    dashboard: slug дашборда (пусто = дефолтный, например 'home' для /dashboard-home)
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        msg: dict = {"type": "lovelace/config", "force": True}
        if dashboard:
            msg["url_path"] = dashboard
        result = await _ws_lovelace(msg)
        if not result.get("success"):
            return f"Ошибка WS: {result}"
        return json.dumps(result["result"], ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def set_lovelace_config(config: str, dashboard: str = "") -> str:
    """
    Записать конфигурацию дашборда Home Assistant (Lovelace).
    config: полная конфигурация дашборда в виде JSON строки
    dashboard: slug дашборда (пусто = дефолтный)
    ВНИМАНИЕ: полностью заменяет текущую конфигурацию!
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        config_data = json.loads(config)
        msg: dict = {"type": "lovelace/config/save", "config": config_data}
        if dashboard:
            msg["url_path"] = dashboard
        result = await _ws_lovelace(msg)
        if not result.get("success"):
            return f"Ошибка WS: {result}"
        return "✓ Конфигурация дашборда обновлена"
    except json.JSONDecodeError:
        return "Ошибка: config должна быть валидным JSON"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def create_automation(
    alias: str,
    trigger: str,
    action: str,
    condition: str = "[]",
    description: str = "",
    mode: str = "single",
) -> str:
    """
    Создать новую автоматизацию в Home Assistant.
    alias: название автоматизации
    trigger: JSON список триггеров
    action: JSON список действий
    condition: JSON список условий (опционально, по умолчанию пусто)
    description: описание (опционально)
    mode: single | restart | queued | parallel
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        automation_id = uuid.uuid4().hex[:16]
        config = {
            "id": automation_id,
            "alias": alias,
            "description": description,
            "trigger": json.loads(trigger),
            "condition": json.loads(condition),
            "action": json.loads(action),
            "mode": mode,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{HA_URL}/api/config/automation/config/{automation_id}",
                headers=_headers(),
                json=config,
            )
            r.raise_for_status()
        await _post("/services/automation/reload", {})
        return f"✓ Автоматизация '{alias}' создана (ID: {automation_id})"
    except json.JSONDecodeError as e:
        return f"Ошибка JSON: {e}"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def delete_automation(automation_id: str) -> str:
    """
    Удалить автоматизацию по ID.
    automation_id: ID из entity_id (например для automation.my_auto → 'my_auto',
                   или числовой/hex ID из create_automation)
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(
                f"{HA_URL}/api/config/automation/config/{automation_id}",
                headers=_headers(),
            )
            r.raise_for_status()
        await _post("/services/automation/reload", {})
        return f"✓ Автоматизация {automation_id} удалена"
    except httpx.HTTPStatusError as e:
        return f"Ошибка HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def create_zone(
    name: str,
    latitude: float,
    longitude: float,
    radius: float,
    icon: str = "mdi:map-marker",
    passive: bool = False,
) -> str:
    """
    Создать зону в Home Assistant.
    name: название зоны
    latitude: широта
    longitude: долгота
    radius: радиус в метрах
    icon: иконка MDI (опционально)
    passive: True = зона не влияет на статус person (только для триггеров)
    """
    if not HA_URL or not HA_TOKEN:
        return "Ошибка: HA_URL или HA_TOKEN не настроены в .env"
    try:
        result = await _ws_lovelace({
            "type": "zone/create",
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "icon": icon,
            "passive": passive,
        })
        if not result.get("success"):
            return f"Ошибка WS: {result}"
        zone_id = result.get("result", {}).get("id", "")
        return f"✓ Зона '{name}' создана (ID: {zone_id})"
    except Exception as e:
        return f"Ошибка: {e}"


if __name__ == "__main__":
    mcp.run()
