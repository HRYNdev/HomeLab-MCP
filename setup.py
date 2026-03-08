"""
HomeLab MCP — интерактивный визард настройки.
Выбирает нужные серверы, собирает .env и claude_desktop_config.json.
"""

import json
import os
import secrets
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.system("chcp 65001 > nul 2>&1")

ENV_PATH = Path(__file__).parent / ".env"
CONFIG_PATH = Path(__file__).parent / "mcp_config.json"

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
DIM = "\033[2m"
BLUE = "\033[94m"


def c(text, color):
    return f"{color}{text}{RESET}"


# ── Переводы ─────────────────────────────────────────────────────────────────

STRINGS = {
    "en": {
        "welcome": "Welcome! This wizard will configure MCP servers",
        "welcome_sub": "only for services you actually have.\n",
        "env_found": "Found .env. Overwrite?",
        "cancelled": "Cancelled.",
        "choose_example": "Example:",
        "choose_input": "Choice",
        "yes_no_y": "[Y/n]",
        "yes_no_n": "[y/N]",
        # Steps
        "step_smarthome": "Smart Home",
        "step_router": "Router",
        "step_servers": "Servers",
        "step_services": "Services",
        "step_saving": "Saving",
        "step_done": "Done!",
        # Questions
        "q_has_ha": "Do you have Home Assistant?",
        "q_manage_router": "Do you want to manage your router via Claude?",
        "q_which_servers": "Which servers do you have?",
        "q_which_services": "Which services are installed? (multiple, space-separated)",
        "q_use_api_token": "Use API Token (recommended)?",
        "q_use_service_token": "Use Service account token?",
        "q_use_api_key": "Use API Key?",
        "q_use_ssh_key": "Use SSH key instead of password?",
        # Router options
        "router_openwrt": "OpenWRT (SSH)",
        "router_opnsense": "OPNsense (REST API)",
        "router_mikrotik": "MikroTik RouterOS 7.1+ (REST API)",
        "router_none": "No router / not sure",
        "router_fw": "Which firmware is on your router?",
        # Server options
        "srv_pi": "Raspberry Pi / Linux server (SSH)",
        "srv_proxmox": "Proxmox VE (virtualization)",
        "srv_none": "No servers",
        # Service options
        "svc_adguard": "AdGuard Home (DNS + ad blocking)",
        "svc_pihole": "Pi-hole (DNS + ad blocking)",
        "svc_uptime_kuma": "Uptime Kuma (uptime monitoring)",
        "svc_portainer": "Portainer (Docker management)",
        "svc_grafana": "Grafana (dashboards & metrics)",
        "svc_truenas": "TrueNAS (NAS / storage)",
        "svc_jellyfin": "Jellyfin (media server)",
        # Hints
        "hint_ha_token": "Token: Settings → Profile → Long-lived access tokens → Create Token",
        "hint_opnsense_key": "API keys: System → Access → Users → your user → API keys → +",
        "hint_proxmox_token": "Token: Datacenter → Permissions → API Tokens → Add",
        "hint_portainer_token": "API Token: Account → Access tokens → Add access token (recommended)",
        "hint_grafana_token": "Service account token: Administration → Service accounts → Add → Add token",
        "hint_truenas_key": "API Key: Top-right menu → API Keys → Add",
        "hint_jellyfin_key": "Key: Dashboard → API Keys → +",
        "hint_uptime_kuma_slug": "Slug: Settings → Status Pages → your slug (e.g. 'default')",
        # Fields
        "f_url": "URL",
        "f_token": "Long-lived access token",
        "f_ip": "Router IP",
        "f_ssh_port": "SSH port",
        "f_ssh_user": "SSH user",
        "f_ssh_pass": "SSH password",
        "f_ip_host": "IP / hostname",
        "f_port": "Port",
        "f_user": "User",
        "f_pass": "Password",
        "f_api_key": "API Key",
        "f_api_secret": "API Secret",
        "f_key_path": "Key path",
        "f_token_id": "Token ID (user@realm!tokenname)",
        "f_token_secret": "Token secret",
        "f_access_token": "Access token",
        "f_service_token": "Token",
        "f_slug": "Status page slug",
        "f_login": "Login",
        # Status
        "added_ha": "Home Assistant added",
        "added_openwrt": "OpenWRT added",
        "added_opnsense": "OPNsense added",
        "added_mikrotik": "MikroTik added",
        "added_pi": "Linux server added",
        "added_adguard": "AdGuard Home added",
        "added_pihole": "Pi-hole added",
        "added_uptime_kuma": "Uptime Kuma added",
        "added_proxmox": "Proxmox added",
        "added_portainer": "Portainer added",
        "added_grafana": "Grafana added",
        "added_truenas": "TrueNAS added",
        "added_jellyfin": "Jellyfin added",
        "skipped_router": "Router skipped",
        "no_services": "No services selected. Re-run setup.py.",
        "env_saved": ".env saved ({n} variables)",
        "config_saved": "mcp_config.json saved ({n} servers)",
        "claude_registered": "Servers registered in Claude Desktop ({path})",
        "next_steps": "Next steps:",
        "install_deps": "1. Install dependencies:",
        "restart_claude": "2. Restart Claude Desktop\n",
        "examples_title": "Example commands that now work:",
        "selected_servers": "Selected servers:",
        # Section names
        "sec_ha": "Home Assistant",
        "sec_router": "Router",
        "sec_pi": "Raspberry Pi / Linux Server",
        "sec_adguard": "AdGuard Home",
        "sec_pihole": "Pi-hole",
        "sec_uptime": "Uptime Kuma",
        "sec_proxmox": "Proxmox VE",
        "sec_jellyfin": "Jellyfin",
        "sec_portainer": "Portainer",
        "sec_grafana": "Grafana",
        "sec_truenas": "TrueNAS SCALE/CORE",
        # Examples
        "ex_ha": '"Show all home devices"',
        "ex_router": '"Who is connected to WiFi?"',
        "ex_pi": '"Which Docker containers are running?"',
        "ex_dns": '"Block ads.example.com"',
        "ex_proxmox": '"Start VM with ID 100"',
        "ex_portainer": '"Show all Docker containers"',
        "ex_grafana": '"Are there any active alerts in Grafana?"',
        "ex_truenas": '"What is the ZFS pool status?"',
        "ex_jellyfin": '"What is being watched on Jellyfin?"',
        # HTTPS port
        "f_https_port": "HTTPS port",
        "no": "No",
    },
    "ru": {
        "welcome": "Добро пожаловать! Этот визард настроит MCP серверы",
        "welcome_sub": "только для тех сервисов которые у вас реально есть.\n",
        "env_found": "Найден .env. Перезаписать?",
        "cancelled": "Отменено.",
        "choose_example": "Пример:",
        "choose_input": "Выбор",
        "yes_no_y": "[Y/n]",
        "yes_no_n": "[y/N]",
        "step_smarthome": "Умный дом",
        "step_router": "Роутер",
        "step_servers": "Серверы",
        "step_services": "Сервисы",
        "step_saving": "Сохранение",
        "step_done": "Готово!",
        "q_has_ha": "Есть Home Assistant?",
        "q_manage_router": "Хотите управлять роутером через Claude?",
        "q_which_servers": "Какие серверы у вас есть?",
        "q_which_services": "Какие сервисы установлены? (можно несколько, через пробел)",
        "q_use_api_token": "Использовать API Token (рекомендуется)?",
        "q_use_service_token": "Использовать Service account token?",
        "q_use_api_key": "Использовать API Key?",
        "q_use_ssh_key": "Использовать SSH ключ вместо пароля?",
        "router_openwrt": "OpenWRT (SSH)",
        "router_opnsense": "OPNsense (REST API)",
        "router_mikrotik": "MikroTik RouterOS 7.1+ (REST API)",
        "router_none": "Нет роутера / не знаю",
        "router_fw": "Какая прошивка на вашем роутере?",
        "srv_pi": "Raspberry Pi / Linux сервер (SSH)",
        "srv_proxmox": "Proxmox VE (виртуализация)",
        "srv_none": "Нет серверов",
        "svc_adguard": "AdGuard Home (DNS + блокировка рекламы)",
        "svc_pihole": "Pi-hole (DNS + блокировка рекламы)",
        "svc_uptime_kuma": "Uptime Kuma (мониторинг доступности)",
        "svc_portainer": "Portainer (управление Docker)",
        "svc_grafana": "Grafana (дашборды и метрики)",
        "svc_truenas": "TrueNAS (NAS / хранилище)",
        "svc_jellyfin": "Jellyfin (медиасервер)",
        "hint_ha_token": "Токен: Settings → Profile → Long-lived access tokens → Create Token",
        "hint_opnsense_key": "API ключи: System → Access → Users → ваш юзер → API keys → +",
        "hint_proxmox_token": "Токен: Datacenter → Permissions → API Tokens → Add",
        "hint_portainer_token": "API Token: Account → Access tokens → Add access token (рекомендуется)",
        "hint_grafana_token": "Service account token: Administration → Service accounts → Add → Add token",
        "hint_truenas_key": "API Key: меню сверху справа → API Keys → Add",
        "hint_jellyfin_key": "Ключ: Dashboard → API Keys → +",
        "hint_uptime_kuma_slug": "Slug: Settings → Status Pages → ваш slug (например 'default')",
        "f_url": "URL",
        "f_token": "Long-lived access token",
        "f_ip": "IP роутера",
        "f_ssh_port": "SSH порт",
        "f_ssh_user": "SSH пользователь",
        "f_ssh_pass": "SSH пароль",
        "f_ip_host": "IP / hostname",
        "f_port": "Порт",
        "f_user": "Пользователь",
        "f_pass": "Пароль",
        "f_api_key": "API Key",
        "f_api_secret": "API Secret",
        "f_key_path": "Путь к ключу",
        "f_token_id": "Token ID (user@realm!tokenname)",
        "f_token_secret": "Token secret",
        "f_access_token": "Access token",
        "f_service_token": "Token",
        "f_slug": "Slug статус-страницы",
        "f_login": "Логин",
        "added_ha": "Home Assistant добавлен",
        "added_openwrt": "OpenWRT добавлен",
        "added_opnsense": "OPNsense добавлен",
        "added_mikrotik": "MikroTik добавлен",
        "added_pi": "Linux сервер добавлен",
        "added_adguard": "AdGuard Home добавлен",
        "added_pihole": "Pi-hole добавлен",
        "added_uptime_kuma": "Uptime Kuma добавлен",
        "added_proxmox": "Proxmox добавлен",
        "added_portainer": "Portainer добавлен",
        "added_grafana": "Grafana добавлен",
        "added_truenas": "TrueNAS добавлен",
        "added_jellyfin": "Jellyfin добавлен",
        "skipped_router": "Роутер пропущен",
        "no_services": "Ни один сервис не выбран. Запустите setup.py снова.",
        "env_saved": ".env сохранён ({n} переменных)",
        "config_saved": "mcp_config.json сохранён ({n} серверов)",
        "claude_registered": "Серверы зарегистрированы в Claude Desktop ({path})",
        "next_steps": "Следующие шаги:",
        "install_deps": "1. Установить зависимости:",
        "restart_claude": "2. Перезапустить Claude Desktop\n",
        "examples_title": "Примеры команд которые теперь работают:",
        "selected_servers": "Выбранные серверы:",
        "sec_ha": "Home Assistant",
        "sec_router": "Роутер",
        "sec_pi": "Linux сервер / Raspberry Pi",
        "sec_adguard": "AdGuard Home",
        "sec_pihole": "Pi-hole",
        "sec_uptime": "Uptime Kuma",
        "sec_proxmox": "Proxmox VE",
        "sec_jellyfin": "Jellyfin",
        "sec_portainer": "Portainer",
        "sec_grafana": "Grafana",
        "sec_truenas": "TrueNAS SCALE/CORE",
        "ex_ha": '"Покажи все устройства дома"',
        "ex_router": '"Кто сейчас подключён к WiFi?"',
        "ex_pi": '"Какие Docker контейнеры запущены?"',
        "ex_dns": '"Заблокируй ads.example.com"',
        "ex_proxmox": '"Запусти виртуалку с ID 100"',
        "ex_portainer": '"Покажи все Docker контейнеры"',
        "ex_grafana": '"Есть ли активные алерты в Grafana?"',
        "ex_truenas": '"Какое состояние ZFS пулов?"',
        "ex_jellyfin": '"Что сейчас смотрят на Jellyfin?"',
        "f_https_port": "HTTPS порт",
        "no": "Нет",
    },
    "de": {
        "welcome": "Willkommen! Dieser Assistent konfiguriert MCP-Server",
        "welcome_sub": "nur für die Dienste, die Sie tatsächlich haben.\n",
        "env_found": ".env gefunden. Überschreiben?",
        "cancelled": "Abgebrochen.",
        "choose_example": "Beispiel:",
        "choose_input": "Auswahl",
        "yes_no_y": "[J/n]",
        "yes_no_n": "[j/N]",
        "step_smarthome": "Smart Home",
        "step_router": "Router",
        "step_servers": "Server",
        "step_services": "Dienste",
        "step_saving": "Speichern",
        "step_done": "Fertig!",
        "q_has_ha": "Haben Sie Home Assistant?",
        "q_manage_router": "Möchten Sie den Router über Claude verwalten?",
        "q_which_servers": "Welche Server haben Sie?",
        "q_which_services": "Welche Dienste sind installiert? (mehrere, durch Leerzeichen getrennt)",
        "q_use_api_token": "API-Token verwenden (empfohlen)?",
        "q_use_service_token": "Service-Account-Token verwenden?",
        "q_use_api_key": "API-Key verwenden?",
        "q_use_ssh_key": "SSH-Schlüssel statt Passwort verwenden?",
        "router_openwrt": "OpenWRT (SSH)",
        "router_opnsense": "OPNsense (REST API)",
        "router_mikrotik": "MikroTik RouterOS 7.1+ (REST API)",
        "router_none": "Kein Router / weiß nicht",
        "router_fw": "Welche Firmware läuft auf Ihrem Router?",
        "srv_pi": "Raspberry Pi / Linux-Server (SSH)",
        "srv_proxmox": "Proxmox VE (Virtualisierung)",
        "srv_none": "Keine Server",
        "svc_adguard": "AdGuard Home (DNS + Werbeblocker)",
        "svc_pihole": "Pi-hole (DNS + Werbeblocker)",
        "svc_uptime_kuma": "Uptime Kuma (Verfügbarkeitsüberwachung)",
        "svc_portainer": "Portainer (Docker-Verwaltung)",
        "svc_grafana": "Grafana (Dashboards & Metriken)",
        "svc_truenas": "TrueNAS (NAS / Speicher)",
        "svc_jellyfin": "Jellyfin (Medienserver)",
        "hint_ha_token": "Token: Settings → Profile → Long-lived access tokens → Create Token",
        "hint_opnsense_key": "API-Schlüssel: System → Access → Users → Ihr Benutzer → API keys → +",
        "hint_proxmox_token": "Token: Datacenter → Permissions → API Tokens → Add",
        "hint_portainer_token": "API Token: Account → Access tokens → Add access token (empfohlen)",
        "hint_grafana_token": "Service-Account-Token: Administration → Service accounts → Add → Add token",
        "hint_truenas_key": "API Key: Menü oben rechts → API Keys → Add",
        "hint_jellyfin_key": "Schlüssel: Dashboard → API Keys → +",
        "hint_uptime_kuma_slug": "Slug: Settings → Status Pages → Ihr Slug (z.B. 'default')",
        "f_url": "URL",
        "f_token": "Long-lived access token",
        "f_ip": "Router-IP",
        "f_ssh_port": "SSH-Port",
        "f_ssh_user": "SSH-Benutzer",
        "f_ssh_pass": "SSH-Passwort",
        "f_ip_host": "IP / Hostname",
        "f_port": "Port",
        "f_user": "Benutzer",
        "f_pass": "Passwort",
        "f_api_key": "API-Key",
        "f_api_secret": "API-Secret",
        "f_key_path": "Schlüsselpfad",
        "f_token_id": "Token-ID (user@realm!tokenname)",
        "f_token_secret": "Token-Secret",
        "f_access_token": "Access token",
        "f_service_token": "Token",
        "f_slug": "Status-Seiten-Slug",
        "f_login": "Anmeldung",
        "added_ha": "Home Assistant hinzugefügt",
        "added_openwrt": "OpenWRT hinzugefügt",
        "added_opnsense": "OPNsense hinzugefügt",
        "added_mikrotik": "MikroTik hinzugefügt",
        "added_pi": "Linux-Server hinzugefügt",
        "added_adguard": "AdGuard Home hinzugefügt",
        "added_pihole": "Pi-hole hinzugefügt",
        "added_uptime_kuma": "Uptime Kuma hinzugefügt",
        "added_proxmox": "Proxmox hinzugefügt",
        "added_portainer": "Portainer hinzugefügt",
        "added_grafana": "Grafana hinzugefügt",
        "added_truenas": "TrueNAS hinzugefügt",
        "added_jellyfin": "Jellyfin hinzugefügt",
        "skipped_router": "Router übersprungen",
        "no_services": "Keine Dienste ausgewählt. setup.py erneut ausführen.",
        "env_saved": ".env gespeichert ({n} Variablen)",
        "config_saved": "mcp_config.json gespeichert ({n} Server)",
        "claude_registered": "Server in Claude Desktop registriert ({path})",
        "next_steps": "Nächste Schritte:",
        "install_deps": "1. Abhängigkeiten installieren:",
        "restart_claude": "2. Claude Desktop neu starten\n",
        "examples_title": "Beispielbefehle die jetzt funktionieren:",
        "selected_servers": "Ausgewählte Server:",
        "sec_ha": "Home Assistant",
        "sec_router": "Router",
        "sec_pi": "Linux-Server / Raspberry Pi",
        "sec_adguard": "AdGuard Home",
        "sec_pihole": "Pi-hole",
        "sec_uptime": "Uptime Kuma",
        "sec_proxmox": "Proxmox VE",
        "sec_jellyfin": "Jellyfin",
        "sec_portainer": "Portainer",
        "sec_grafana": "Grafana",
        "sec_truenas": "TrueNAS SCALE/CORE",
        "ex_ha": '"Zeige alle Heimgeräte"',
        "ex_router": '"Wer ist mit dem WLAN verbunden?"',
        "ex_pi": '"Welche Docker-Container laufen?"',
        "ex_dns": '"Blockiere ads.example.com"',
        "ex_proxmox": '"Starte VM mit ID 100"',
        "ex_portainer": '"Zeige alle Docker-Container"',
        "ex_grafana": '"Gibt es aktive Grafana-Alarme?"',
        "ex_truenas": '"Wie ist der ZFS-Pool-Status?"',
        "ex_jellyfin": '"Was wird auf Jellyfin geschaut?"',
        "f_https_port": "HTTPS-Port",
        "no": "Nein",
    },
    "es": {
        "welcome": "¡Bienvenido! Este asistente configurará los servidores MCP",
        "welcome_sub": "solo para los servicios que realmente tienes.\n",
        "env_found": "Se encontró .env. ¿Sobreescribir?",
        "cancelled": "Cancelado.",
        "choose_example": "Ejemplo:",
        "choose_input": "Selección",
        "yes_no_y": "[S/n]",
        "yes_no_n": "[s/N]",
        "step_smarthome": "Casa inteligente",
        "step_router": "Router",
        "step_servers": "Servidores",
        "step_services": "Servicios",
        "step_saving": "Guardando",
        "step_done": "¡Listo!",
        "q_has_ha": "¿Tienes Home Assistant?",
        "q_manage_router": "¿Quieres gestionar el router con Claude?",
        "q_which_servers": "¿Qué servidores tienes?",
        "q_which_services": "¿Qué servicios están instalados? (varios, separados por espacio)",
        "q_use_api_token": "¿Usar API Token (recomendado)?",
        "q_use_service_token": "¿Usar Service account token?",
        "q_use_api_key": "¿Usar API Key?",
        "q_use_ssh_key": "¿Usar clave SSH en lugar de contraseña?",
        "router_openwrt": "OpenWRT (SSH)",
        "router_opnsense": "OPNsense (REST API)",
        "router_mikrotik": "MikroTik RouterOS 7.1+ (REST API)",
        "router_none": "Sin router / no sé",
        "router_fw": "¿Qué firmware tiene tu router?",
        "srv_pi": "Raspberry Pi / servidor Linux (SSH)",
        "srv_proxmox": "Proxmox VE (virtualización)",
        "srv_none": "Sin servidores",
        "svc_adguard": "AdGuard Home (DNS + bloqueo de anuncios)",
        "svc_pihole": "Pi-hole (DNS + bloqueo de anuncios)",
        "svc_uptime_kuma": "Uptime Kuma (monitoreo de disponibilidad)",
        "svc_portainer": "Portainer (gestión de Docker)",
        "svc_grafana": "Grafana (paneles y métricas)",
        "svc_truenas": "TrueNAS (NAS / almacenamiento)",
        "svc_jellyfin": "Jellyfin (servidor multimedia)",
        "hint_ha_token": "Token: Settings → Profile → Long-lived access tokens → Create Token",
        "hint_opnsense_key": "Claves API: System → Access → Users → tu usuario → API keys → +",
        "hint_proxmox_token": "Token: Datacenter → Permissions → API Tokens → Add",
        "hint_portainer_token": "API Token: Account → Access tokens → Add access token (recomendado)",
        "hint_grafana_token": "Service account token: Administration → Service accounts → Add → Add token",
        "hint_truenas_key": "API Key: menú superior derecho → API Keys → Add",
        "hint_jellyfin_key": "Clave: Dashboard → API Keys → +",
        "hint_uptime_kuma_slug": "Slug: Settings → Status Pages → tu slug (p.ej. 'default')",
        "f_url": "URL",
        "f_token": "Long-lived access token",
        "f_ip": "IP del router",
        "f_ssh_port": "Puerto SSH",
        "f_ssh_user": "Usuario SSH",
        "f_ssh_pass": "Contraseña SSH",
        "f_ip_host": "IP / hostname",
        "f_port": "Puerto",
        "f_user": "Usuario",
        "f_pass": "Contraseña",
        "f_api_key": "API Key",
        "f_api_secret": "API Secret",
        "f_key_path": "Ruta de la clave",
        "f_token_id": "Token ID (user@realm!tokenname)",
        "f_token_secret": "Token secret",
        "f_access_token": "Access token",
        "f_service_token": "Token",
        "f_slug": "Slug de la página de estado",
        "f_login": "Inicio de sesión",
        "added_ha": "Home Assistant añadido",
        "added_openwrt": "OpenWRT añadido",
        "added_opnsense": "OPNsense añadido",
        "added_mikrotik": "MikroTik añadido",
        "added_pi": "Servidor Linux añadido",
        "added_adguard": "AdGuard Home añadido",
        "added_pihole": "Pi-hole añadido",
        "added_uptime_kuma": "Uptime Kuma añadido",
        "added_proxmox": "Proxmox añadido",
        "added_portainer": "Portainer añadido",
        "added_grafana": "Grafana añadido",
        "added_truenas": "TrueNAS añadido",
        "added_jellyfin": "Jellyfin añadido",
        "skipped_router": "Router omitido",
        "no_services": "No se seleccionó ningún servicio. Ejecuta setup.py de nuevo.",
        "env_saved": ".env guardado ({n} variables)",
        "config_saved": "mcp_config.json guardado ({n} servidores)",
        "claude_registered": "Servidores registrados en Claude Desktop ({path})",
        "next_steps": "Siguientes pasos:",
        "install_deps": "1. Instalar dependencias:",
        "restart_claude": "2. Reiniciar Claude Desktop\n",
        "examples_title": "Ejemplos de comandos que ahora funcionan:",
        "selected_servers": "Servidores seleccionados:",
        "sec_ha": "Home Assistant",
        "sec_router": "Router",
        "sec_pi": "Servidor Linux / Raspberry Pi",
        "sec_adguard": "AdGuard Home",
        "sec_pihole": "Pi-hole",
        "sec_uptime": "Uptime Kuma",
        "sec_proxmox": "Proxmox VE",
        "sec_jellyfin": "Jellyfin",
        "sec_portainer": "Portainer",
        "sec_grafana": "Grafana",
        "sec_truenas": "TrueNAS SCALE/CORE",
        "ex_ha": '"Muestra todos los dispositivos del hogar"',
        "ex_router": '"¿Quién está conectado al WiFi?"',
        "ex_pi": '"¿Qué contenedores Docker están corriendo?"',
        "ex_dns": '"Bloquea ads.example.com"',
        "ex_proxmox": '"Inicia la VM con ID 100"',
        "ex_portainer": '"Muestra todos los contenedores Docker"',
        "ex_grafana": '"¿Hay alertas activas en Grafana?"',
        "ex_truenas": '"¿Cuál es el estado del pool ZFS?"',
        "ex_jellyfin": '"¿Qué se está viendo en Jellyfin?"',
        "f_https_port": "Puerto HTTPS",
        "no": "No",
    },
    "fr": {
        "welcome": "Bienvenue ! Cet assistant configurera les serveurs MCP",
        "welcome_sub": "uniquement pour les services que vous avez réellement.\n",
        "env_found": "Fichier .env trouvé. Écraser ?",
        "cancelled": "Annulé.",
        "choose_example": "Exemple :",
        "choose_input": "Choix",
        "yes_no_y": "[O/n]",
        "yes_no_n": "[o/N]",
        "step_smarthome": "Maison intelligente",
        "step_router": "Routeur",
        "step_servers": "Serveurs",
        "step_services": "Services",
        "step_saving": "Sauvegarde",
        "step_done": "Terminé !",
        "q_has_ha": "Avez-vous Home Assistant ?",
        "q_manage_router": "Voulez-vous gérer le routeur via Claude ?",
        "q_which_servers": "Quels serveurs avez-vous ?",
        "q_which_services": "Quels services sont installés ? (plusieurs, séparés par espace)",
        "q_use_api_token": "Utiliser un API Token (recommandé) ?",
        "q_use_service_token": "Utiliser un Service account token ?",
        "q_use_api_key": "Utiliser une API Key ?",
        "q_use_ssh_key": "Utiliser une clé SSH au lieu du mot de passe ?",
        "router_openwrt": "OpenWRT (SSH)",
        "router_opnsense": "OPNsense (REST API)",
        "router_mikrotik": "MikroTik RouterOS 7.1+ (REST API)",
        "router_none": "Pas de routeur / je ne sais pas",
        "router_fw": "Quel firmware est sur votre routeur ?",
        "srv_pi": "Raspberry Pi / serveur Linux (SSH)",
        "srv_proxmox": "Proxmox VE (virtualisation)",
        "srv_none": "Pas de serveurs",
        "svc_adguard": "AdGuard Home (DNS + bloqueur de publicités)",
        "svc_pihole": "Pi-hole (DNS + bloqueur de publicités)",
        "svc_uptime_kuma": "Uptime Kuma (surveillance de disponibilité)",
        "svc_portainer": "Portainer (gestion Docker)",
        "svc_grafana": "Grafana (tableaux de bord & métriques)",
        "svc_truenas": "TrueNAS (NAS / stockage)",
        "svc_jellyfin": "Jellyfin (serveur multimédia)",
        "hint_ha_token": "Token : Settings → Profile → Long-lived access tokens → Create Token",
        "hint_opnsense_key": "Clés API : System → Access → Users → votre utilisateur → API keys → +",
        "hint_proxmox_token": "Token : Datacenter → Permissions → API Tokens → Add",
        "hint_portainer_token": "API Token : Account → Access tokens → Add access token (recommandé)",
        "hint_grafana_token": "Service account token : Administration → Service accounts → Add → Add token",
        "hint_truenas_key": "API Key : menu en haut à droite → API Keys → Add",
        "hint_jellyfin_key": "Clé : Dashboard → API Keys → +",
        "hint_uptime_kuma_slug": "Slug : Settings → Status Pages → votre slug (ex. 'default')",
        "f_url": "URL",
        "f_token": "Long-lived access token",
        "f_ip": "IP du routeur",
        "f_ssh_port": "Port SSH",
        "f_ssh_user": "Utilisateur SSH",
        "f_ssh_pass": "Mot de passe SSH",
        "f_ip_host": "IP / hostname",
        "f_port": "Port",
        "f_user": "Utilisateur",
        "f_pass": "Mot de passe",
        "f_api_key": "API Key",
        "f_api_secret": "API Secret",
        "f_key_path": "Chemin de la clé",
        "f_token_id": "Token ID (user@realm!tokenname)",
        "f_token_secret": "Token secret",
        "f_access_token": "Access token",
        "f_service_token": "Token",
        "f_slug": "Slug de la page de statut",
        "f_login": "Connexion",
        "added_ha": "Home Assistant ajouté",
        "added_openwrt": "OpenWRT ajouté",
        "added_opnsense": "OPNsense ajouté",
        "added_mikrotik": "MikroTik ajouté",
        "added_pi": "Serveur Linux ajouté",
        "added_adguard": "AdGuard Home ajouté",
        "added_pihole": "Pi-hole ajouté",
        "added_uptime_kuma": "Uptime Kuma ajouté",
        "added_proxmox": "Proxmox ajouté",
        "added_portainer": "Portainer ajouté",
        "added_grafana": "Grafana ajouté",
        "added_truenas": "TrueNAS ajouté",
        "added_jellyfin": "Jellyfin ajouté",
        "skipped_router": "Routeur ignoré",
        "no_services": "Aucun service sélectionné. Relancez setup.py.",
        "env_saved": ".env sauvegardé ({n} variables)",
        "config_saved": "mcp_config.json sauvegardé ({n} serveurs)",
        "claude_registered": "Serveurs enregistrés dans Claude Desktop ({path})",
        "next_steps": "Étapes suivantes :",
        "install_deps": "1. Installer les dépendances :",
        "restart_claude": "2. Redémarrer Claude Desktop\n",
        "examples_title": "Exemples de commandes qui fonctionnent maintenant :",
        "selected_servers": "Serveurs sélectionnés :",
        "sec_ha": "Home Assistant",
        "sec_router": "Routeur",
        "sec_pi": "Serveur Linux / Raspberry Pi",
        "sec_adguard": "AdGuard Home",
        "sec_pihole": "Pi-hole",
        "sec_uptime": "Uptime Kuma",
        "sec_proxmox": "Proxmox VE",
        "sec_jellyfin": "Jellyfin",
        "sec_portainer": "Portainer",
        "sec_grafana": "Grafana",
        "sec_truenas": "TrueNAS SCALE/CORE",
        "ex_ha": '"Afficher tous les appareils domestiques"',
        "ex_router": '"Qui est connecté au WiFi ?"',
        "ex_pi": '"Quels conteneurs Docker tournent ?"',
        "ex_dns": '"Bloquer ads.example.com"',
        "ex_proxmox": '"Démarrer la VM avec l\'ID 100"',
        "ex_portainer": '"Afficher tous les conteneurs Docker"',
        "ex_grafana": '"Y a-t-il des alertes actives dans Grafana ?"',
        "ex_truenas": '"Quel est l\'état des pools ZFS ?"',
        "ex_jellyfin": '"Qu\'est-ce qui est regardé sur Jellyfin ?"',
        "f_https_port": "Port HTTPS",
        "no": "Non",
    },
}

# Глобальный словарь активного языка
S: dict = STRINGS["en"]


def ask(prompt, default="", secret=False):
    hint = f" [{default}]" if default else ""
    full = f"    {prompt}{c(hint, DIM)}: "
    try:
        if secret and sys.stdin.isatty():
            import getpass
            val = getpass.getpass(full)
        else:
            val = input(full).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    return val if val else default


def choose(prompt, options: list[tuple[str, str]], multi=False) -> list[int] | int:
    print(f"\n  {c(prompt, BOLD)}")
    for i, (key, label) in enumerate(options):
        print(f"    {c(str(i), CYAN)}. {label}")
    if multi:
        print(f"    {c(S['choose_example'], DIM)} 0 2 4  (Enter = skip all)")
    try:
        raw = input(f"    {c(S['choose_input'], BOLD)}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)

    if not raw:
        return [] if multi else 0

    if multi:
        parts = raw.replace(",", " ").split()
        result = []
        for p in parts:
            if p.isdigit() and 0 <= int(p) < len(options):
                result.append(int(p))
        return result
    else:
        if raw.isdigit() and 0 <= int(raw) < len(options):
            return int(raw)
        return 0


def ok(msg):
    print(f"  {c('✓', GREEN)} {msg}")


def warn(msg):
    print(f"  {c('!', YELLOW)} {msg}")


def header(title):
    w = 46
    print(f"\n{c('=' * w, CYAN)}")
    pad = (w - len(title) - 2) // 2
    print(f"{c('=' * pad + ' ' + title + ' ' + '=' * (w - pad - len(title) - 2), CYAN)}")
    print(f"{c('=' * w, CYAN)}")


def section(title):
    print(f"\n  {c('-- ' + title, BOLD + BLUE)}")


def yn(key_y: str) -> bool:
    """Ask yes/no, return True if yes. Default = yes (Enter)."""
    question = S[key_y]
    yn_hint = S["yes_no_y"]
    try:
        ans = input(f"    {question} {c(yn_hint, DIM)}: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    # Accept y/yes/j/ja/s/si/o/oui as "yes"; empty = yes (default)
    return ans in ("y", "yes", "j", "ja", "s", "si", "o", "oui", "")


# ── Сборщики конфига по сервисам ────────────────────────────────────────────────

def setup_ha(env: dict, servers: dict):
    section(S["sec_ha"])
    env["HA_URL"] = ask(S["f_url"], "http://homeassistant.local:8123")
    print(f"    {c(S['hint_ha_token'], DIM)}")
    env["HA_TOKEN"] = ask(S["f_token"], secret=True)
    servers["homeassistant"] = {"file": "ha_server.py", "name": "Home Assistant"}
    ok(S["added_ha"])


def setup_router(env: dict, servers: dict):
    section(S["sec_router"])
    router_options = [
        ("openwrt",  S["router_openwrt"]),
        ("opnsense", S["router_opnsense"]),
        ("mikrotik", S["router_mikrotik"]),
        ("none",     S["router_none"]),
    ]
    choice = choose(S["router_fw"], router_options)

    if choice == 0:
        env["OPENWRT_HOST"] = ask(S["f_ip"], "192.168.1.1")
        env["OPENWRT_PORT"] = ask(S["f_ssh_port"], "22")
        env["OPENWRT_USER"] = ask(S["f_ssh_user"], "root")
        env["OPENWRT_PASSWORD"] = ask(S["f_ssh_pass"], secret=True)
        servers["openwrt"] = {"file": "openwrt_server.py", "name": "OpenWRT"}
        ok(S["added_openwrt"])
    elif choice == 1:
        env["OPNSENSE_HOST"] = ask(S["f_ip"], "192.168.1.1")
        env["OPNSENSE_PORT"] = ask(S["f_https_port"], "443")
        print(f"    {c(S['hint_opnsense_key'], DIM)}")
        env["OPNSENSE_KEY"] = ask(S["f_api_key"])
        env["OPNSENSE_SECRET"] = ask(S["f_api_secret"], secret=True)
        env["OPNSENSE_VERIFY_SSL"] = "false"
        servers["opnsense"] = {"file": "opnsense_server.py", "name": "OPNsense"}
        ok(S["added_opnsense"])
    elif choice == 2:
        env["MIKROTIK_HOST"] = ask(S["f_ip"], "192.168.1.1")
        env["MIKROTIK_PORT"] = ask(S["f_https_port"], "443")
        env["MIKROTIK_USER"] = ask(S["f_user"], "admin")
        env["MIKROTIK_PASSWORD"] = ask(S["f_pass"], secret=True)
        env["MIKROTIK_VERIFY_SSL"] = "false"
        servers["mikrotik"] = {"file": "mikrotik_server.py", "name": "MikroTik"}
        ok(S["added_mikrotik"])
    else:
        warn(S["skipped_router"])


def setup_linux_server(env: dict, servers: dict):
    section(S["sec_pi"])
    env["PI_HOST"] = ask(S["f_ip_host"])
    env["PI_PORT"] = ask(S["f_ssh_port"], "22")
    env["PI_USER"] = ask(S["f_ssh_user"], "pi")
    if yn("q_use_ssh_key"):
        env["PI_KEY_PATH"] = ask(S["f_key_path"], str(Path.home() / ".ssh" / "id_rsa"))
        env["PI_PASSWORD"] = ""
    else:
        env["PI_PASSWORD"] = ask(S["f_ssh_pass"], secret=True)
        env["PI_KEY_PATH"] = ""
    servers["pi"] = {"file": "pi_server.py", "name": "Raspberry Pi / Linux"}
    ok(S["added_pi"])


def setup_adguard(env: dict, servers: dict):
    section(S["sec_adguard"])
    env["ADGUARD_URL"] = ask(S["f_url"], "http://192.168.1.1:3000")
    env["ADGUARD_USER"] = ask(S["f_login"], "admin")
    env["ADGUARD_PASSWORD"] = ask(S["f_pass"], secret=True)
    servers["adguard"] = {"file": "adguard_server.py", "name": "AdGuard Home"}
    ok(S["added_adguard"])


def setup_pihole(env: dict, servers: dict):
    section(S["sec_pihole"])
    env["PIHOLE_URL"] = ask(S["f_url"], "http://pi.hole")
    env["PIHOLE_PASSWORD"] = ask(S["f_pass"], secret=True)
    servers["pihole"] = {"file": "pihole_server.py", "name": "Pi-hole"}
    ok(S["added_pihole"])


def setup_uptime_kuma(env: dict, servers: dict):
    section(S["sec_uptime"])
    env["UPTIME_KUMA_URL"] = ask(S["f_url"], "http://localhost:3001")
    print(f"    {c(S['hint_uptime_kuma_slug'], DIM)}")
    env["UPTIME_KUMA_SLUG"] = ask(S["f_slug"], "default")
    servers["uptime-kuma"] = {"file": "uptime_kuma_server.py", "name": "Uptime Kuma"}
    ok(S["added_uptime_kuma"])


def setup_proxmox(env: dict, servers: dict):
    section(S["sec_proxmox"])
    env["PROXMOX_HOST"] = ask(S["f_ip_host"], "192.168.1.10")
    env["PROXMOX_PORT"] = ask(S["f_port"], "8006")
    env["PROXMOX_USER"] = ask(S["f_user"], "root@pam")
    print(f"    {c(S['hint_proxmox_token'], DIM)}")
    if yn("q_use_api_token"):
        env["PROXMOX_TOKEN_ID"] = ask(S["f_token_id"])
        env["PROXMOX_TOKEN_SECRET"] = ask(S["f_token_secret"], secret=True)
        env["PROXMOX_PASSWORD"] = ""
    else:
        env["PROXMOX_PASSWORD"] = ask(S["f_pass"], secret=True)
        env["PROXMOX_TOKEN_ID"] = ""
        env["PROXMOX_TOKEN_SECRET"] = ""
    env["PROXMOX_VERIFY_SSL"] = "false"
    servers["proxmox"] = {"file": "proxmox_server.py", "name": "Proxmox VE"}
    ok(S["added_proxmox"])


def setup_jellyfin(env: dict, servers: dict):
    section(S["sec_jellyfin"])
    env["JELLYFIN_URL"] = ask(S["f_url"], "http://localhost:8096")
    print(f"    {c(S['hint_jellyfin_key'], DIM)}")
    env["JELLYFIN_API_KEY"] = ask(S["f_api_key"], secret=True)
    servers["jellyfin"] = {"file": "jellyfin_server.py", "name": "Jellyfin"}
    ok(S["added_jellyfin"])


def setup_portainer(env: dict, servers: dict):
    section(S["sec_portainer"])
    env["PORTAINER_URL"] = ask(S["f_url"], "https://localhost:9443")
    print(f"    {c(S['hint_portainer_token'], DIM)}")
    if yn("q_use_api_token"):
        env["PORTAINER_TOKEN"] = ask(S["f_access_token"], secret=True)
        env["PORTAINER_USER"] = ""
        env["PORTAINER_PASSWORD"] = ""
    else:
        env["PORTAINER_TOKEN"] = ""
        env["PORTAINER_USER"] = ask(S["f_user"], "admin")
        env["PORTAINER_PASSWORD"] = ask(S["f_pass"], secret=True)
    env["PORTAINER_VERIFY_SSL"] = "false"
    servers["portainer"] = {"file": "portainer_server.py", "name": "Portainer"}
    ok(S["added_portainer"])


def setup_grafana(env: dict, servers: dict):
    section(S["sec_grafana"])
    env["GRAFANA_URL"] = ask(S["f_url"], "http://localhost:3000")
    print(f"    {c(S['hint_grafana_token'], DIM)}")
    if yn("q_use_service_token"):
        env["GRAFANA_TOKEN"] = ask(S["f_service_token"], secret=True)
        env["GRAFANA_USER"] = ""
        env["GRAFANA_PASSWORD"] = ""
    else:
        env["GRAFANA_TOKEN"] = ""
        env["GRAFANA_USER"] = ask(S["f_login"], "admin")
        env["GRAFANA_PASSWORD"] = ask(S["f_pass"], secret=True)
    servers["grafana"] = {"file": "grafana_server.py", "name": "Grafana"}
    ok(S["added_grafana"])


def setup_truenas(env: dict, servers: dict):
    section(S["sec_truenas"])
    env["TRUENAS_URL"] = ask(S["f_url"], "http://192.168.1.10")
    print(f"    {c(S['hint_truenas_key'], DIM)}")
    if yn("q_use_api_key"):
        env["TRUENAS_API_KEY"] = ask(S["f_api_key"], secret=True)
        env["TRUENAS_USER"] = ""
        env["TRUENAS_PASSWORD"] = ""
    else:
        env["TRUENAS_API_KEY"] = ""
        env["TRUENAS_USER"] = ask(S["f_user"], "root")
        env["TRUENAS_PASSWORD"] = ask(S["f_pass"], secret=True)
    env["TRUENAS_VERIFY_SSL"] = "false"
    servers["truenas"] = {"file": "truenas_server.py", "name": "TrueNAS"}
    ok(S["added_truenas"])


# ── Выбор языка ──────────────────────────────────────────────────────────────

def select_language() -> str:
    """Show language selection without colors/translations (works before init)."""
    lang_options = [
        ("en", "English"),
        ("ru", "Русский"),
        ("de", "Deutsch"),
        ("es", "Español"),
        ("fr", "Français"),
    ]
    print("\n  Select language / Выберите язык:")
    for i, (code, name) in enumerate(lang_options):
        print(f"    {i}. {name}")
    try:
        raw = input("  > ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    if raw.isdigit() and 0 <= int(raw) < len(lang_options):
        return lang_options[int(raw)][0]
    return "en"


# ── Главный визард ──────────────────────────────────────────────────────────────

def main():
    global S

    # ── Шаг 0: Выбор языка ──────────────────────────────────────────────────
    lang = select_language()
    S = STRINGS[lang]

    header("HomeLab MCP Setup")
    print(f"\n  {c(S['welcome'], BOLD)}")
    print(f"  {S['welcome_sub']}")

    if ENV_PATH.exists():
        ans = input(f"  {S['env_found']} {c(S['yes_no_n'], DIM)}: ").strip().lower()
        if ans not in ("y", "yes", "j", "ja", "s", "si", "o", "oui"):
            print(f"  {c(S['cancelled'], DIM)}\n")
            sys.exit(0)

    env: dict[str, str] = {}
    servers: dict[str, dict] = {}

    # ── Шаг 1: Умный дом ────────────────────────────────────────────────────
    header(S["step_smarthome"])
    ha_options = [
        ("ha",   "Home Assistant"),
        ("none", S["no"]),
    ]
    if choose(S["q_has_ha"], ha_options) == 0:
        setup_ha(env, servers)

    # ── Шаг 2: Роутер ───────────────────────────────────────────────────────
    header(S["step_router"])
    try:
        ans = input(f"\n  {S['q_manage_router']} {c(S['yes_no_y'], DIM)}: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)
    if ans not in ("n", "no", "nein", "non"):
        setup_router(env, servers)

    # ── Шаг 3: Серверы ──────────────────────────────────────────────────────
    header(S["step_servers"])
    server_options = [
        ("pi",      S["srv_pi"]),
        ("proxmox", S["srv_proxmox"]),
        ("none",    S["srv_none"]),
    ]
    srv_choices = choose(S["q_which_servers"], server_options, multi=True)

    if 0 in srv_choices:
        setup_linux_server(env, servers)
    if 1 in srv_choices:
        setup_proxmox(env, servers)

    # ── Шаг 4: Сервисы ──────────────────────────────────────────────────────
    header(S["step_services"])
    svc_options = [
        ("adguard",     S["svc_adguard"]),
        ("pihole",      S["svc_pihole"]),
        ("uptime_kuma", S["svc_uptime_kuma"]),
        ("portainer",   S["svc_portainer"]),
        ("grafana",     S["svc_grafana"]),
        ("truenas",     S["svc_truenas"]),
        ("jellyfin",    S["svc_jellyfin"]),
    ]
    svc_choices = choose(S["q_which_services"], svc_options, multi=True)

    if 0 in svc_choices:
        setup_adguard(env, servers)
    if 1 in svc_choices:
        setup_pihole(env, servers)
    if 2 in svc_choices:
        setup_uptime_kuma(env, servers)
    if 3 in svc_choices:
        setup_portainer(env, servers)
    if 4 in svc_choices:
        setup_grafana(env, servers)
    if 5 in svc_choices:
        setup_truenas(env, servers)
    if 6 in svc_choices:
        setup_jellyfin(env, servers)

    # ── Проверка ─────────────────────────────────────────────────────────────
    if not servers:
        print(f"\n  {c(S['no_services'], YELLOW)}\n")
        sys.exit(0)

    # ── Auth ──────────────────────────────────────────────────────────────────
    env["AUTH_MODE"] = "none"
    env["ADMIN_SECRET"] = secrets.token_urlsafe(16)

    # ── Сохраняем .env ────────────────────────────────────────────────────────
    header(S["step_saving"])

    groups = {
        "Home Assistant": ["HA_URL", "HA_TOKEN"],
        "OpenWRT": ["OPENWRT_HOST", "OPENWRT_PORT", "OPENWRT_USER", "OPENWRT_PASSWORD"],
        "OPNsense": ["OPNSENSE_HOST", "OPNSENSE_PORT", "OPNSENSE_KEY", "OPNSENSE_SECRET", "OPNSENSE_VERIFY_SSL"],
        "MikroTik": ["MIKROTIK_HOST", "MIKROTIK_PORT", "MIKROTIK_USER", "MIKROTIK_PASSWORD", "MIKROTIK_VERIFY_SSL"],
        "Linux Server / Raspberry Pi": ["PI_HOST", "PI_PORT", "PI_USER", "PI_PASSWORD", "PI_KEY_PATH"],
        "AdGuard Home": ["ADGUARD_URL", "ADGUARD_USER", "ADGUARD_PASSWORD"],
        "Pi-hole": ["PIHOLE_URL", "PIHOLE_PASSWORD"],
        "Uptime Kuma": ["UPTIME_KUMA_URL", "UPTIME_KUMA_SLUG"],
        "Proxmox": ["PROXMOX_HOST", "PROXMOX_PORT", "PROXMOX_USER", "PROXMOX_PASSWORD",
                    "PROXMOX_TOKEN_ID", "PROXMOX_TOKEN_SECRET", "PROXMOX_VERIFY_SSL"],
        "Portainer": ["PORTAINER_URL", "PORTAINER_TOKEN", "PORTAINER_USER", "PORTAINER_PASSWORD", "PORTAINER_VERIFY_SSL"],
        "Grafana": ["GRAFANA_URL", "GRAFANA_TOKEN", "GRAFANA_USER", "GRAFANA_PASSWORD"],
        "TrueNAS": ["TRUENAS_URL", "TRUENAS_API_KEY", "TRUENAS_USER", "TRUENAS_PASSWORD", "TRUENAS_VERIFY_SSL"],
        "Jellyfin": ["JELLYFIN_URL", "JELLYFIN_API_KEY"],
        "Auth": ["AUTH_MODE", "ADMIN_SECRET"],
    }

    lines = ["# HomeLab MCP — конфигурация (сгенерировано setup.py)\n"]
    for group_name, keys in groups.items():
        group_vals = {k: env.get(k, "") for k in keys}
        if any(group_vals.values()):
            lines.append(f"\n# {group_name}\n")
            for k, v in group_vals.items():
                lines.append(f"{k}={v}\n")

    ENV_PATH.write_text("".join(lines), encoding="utf-8")
    ok(S["env_saved"].format(n=len([l for l in lines if "=" in l])))

    # ── Claude Desktop ────────────────────────────────────────────────────────
    cwd = str(Path(__file__).parent)
    mcp_servers = {}
    for srv_id, info in servers.items():
        mcp_servers[srv_id] = {
            "command": sys.executable,
            "args": [str(Path(cwd) / info["file"])],
            "cwd": cwd,
        }

    CONFIG_PATH.write_text(json.dumps({"mcpServers": mcp_servers}, indent=2, ensure_ascii=False), encoding="utf-8")
    ok(S["config_saved"].format(n=len(servers)))

    claude_config_paths = {
        "win32":  Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
        "darwin": Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        "linux":  Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
    }
    claude_path = claude_config_paths.get(sys.platform, claude_config_paths["linux"])

    if claude_path.exists():
        try:
            existing = json.loads(claude_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}
        claude_path.parent.mkdir(parents=True, exist_ok=True)

    existing.setdefault("mcpServers", {})
    existing["mcpServers"].update(mcp_servers)
    claude_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    ok(S["claude_registered"].format(path=claude_path))

    # ── Итог ──────────────────────────────────────────────────────────────────
    header(S["step_done"])

    print(f"\n  {c(S['selected_servers'], BOLD)}")
    for srv_id, info in servers.items():
        print(f"    {c('•', GREEN)} {info['name']}  {c('(' + info['file'] + ')', DIM)}")

    print(f"\n  {c(S['next_steps'], BOLD)}")
    print(f"\n  {S['install_deps']}")
    print(f"     {c('pip install -r requirements.txt', CYAN)}")
    print(f"\n  {S['restart_claude']}")

    print(f"  {c(S['examples_title'], BOLD)}")
    examples = []
    if "homeassistant" in servers:
        examples.append(S["ex_ha"])
    if "openwrt" in servers or "opnsense" in servers or "mikrotik" in servers:
        examples.append(S["ex_router"])
    if "pi" in servers:
        examples.append(S["ex_pi"])
    if "adguard" in servers or "pihole" in servers:
        examples.append(S["ex_dns"])
    if "proxmox" in servers:
        examples.append(S["ex_proxmox"])
    if "portainer" in servers:
        examples.append(S["ex_portainer"])
    if "grafana" in servers:
        examples.append(S["ex_grafana"])
    if "truenas" in servers:
        examples.append(S["ex_truenas"])
    if "jellyfin" in servers:
        examples.append(S["ex_jellyfin"])

    for ex in examples[:4]:
        print(f"    {c('>>', CYAN)} {ex}")

    print()


if __name__ == "__main__":
    main()
