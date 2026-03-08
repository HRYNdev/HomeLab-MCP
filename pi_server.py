"""MCP сервер для управления Raspberry Pi 4 через SSH/SFTP.

Безопасный доступ: только чтение/запись файлов, Docker, systemd, мониторинг.
Без удалений, без произвольных команд.
"""

import json
import os
import shlex
from pathlib import Path

import asyncssh
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent / ".env")

PI_HOST = os.getenv("PI_HOST", "")
PI_USER = os.getenv("PI_USER", "")
PI_PASSWORD = os.getenv("PI_PASSWORD", "")

mcp = FastMCP("raspberry_pi")


# ── helpers ──────────────────────────────────────────────────────────────────

def _conn_kwargs() -> dict:
    return {
        "host": PI_HOST,
        "username": PI_USER,
        "password": PI_PASSWORD,
        "known_hosts": None,
        "connect_timeout": 10,
    }


def _check_config() -> str | None:
    if not PI_HOST or not PI_USER or not PI_PASSWORD:
        return "Ошибка: PI_HOST, PI_USER или PI_PASSWORD не настроены в .env"
    return None


async def _run(cmd: str) -> str:
    async with asyncssh.connect(**_conn_kwargs()) as conn:
        result = await conn.run(cmd)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.exit_status != 0 and not out:
            return f"Ошибка (exit {result.exit_status}): {err}"
        return out or err


async def _sftp_resolve(sftp, path: str) -> str:
    """SFTP не раскрывает ~, делаем это вручную через realpath."""
    if path.startswith("~"):
        home = await sftp.realpath(".")
        path = home + path[1:]
    return path


# ── Мониторинг системы ────────────────────────────────────────────────────────

@mcp.tool()
async def pi_status() -> str:
    """
    Состояние Raspberry Pi: CPU%, RAM, диск, температура, uptime.
    """
    err = _check_config()
    if err:
        return err
    try:
        script = (
            "echo '=CPU='; top -bn1 | grep 'Cpu(s)' | awk '{print $2}'; "
            "echo '=MEM='; free -m | awk 'NR==2{printf \"%s/%s MB (%.0f%%)\\n\", $3,$2,$3*100/$2}'; "
            "echo '=DISK='; df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'; "
            "echo '=TEMP='; vcgencmd measure_temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.1f°C\\n\", $1/1000}'; "
            "echo '=UPTIME='; uptime -p"
        )
        raw = await _run(script)
        lines = raw.split("\n")
        result: dict[str, str] = {}
        key = None
        for line in lines:
            if line.startswith("=") and line.endswith("="):
                key = line.strip("=").lower()
            elif key and line:
                result[key] = line
                key = None
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_network_status() -> str:
    """
    Сетевой статус Pi: IP-адреса интерфейсов и прослушиваемые порты.
    """
    err = _check_config()
    if err:
        return err
    try:
        script = "echo '=ADDR='; ip -br addr; echo '=PORTS='; ss -tuln | grep LISTEN"
        raw = await _run(script)
        sections = raw.split("=PORTS=")
        addr = sections[0].replace("=ADDR=", "").strip()
        ports = sections[1].strip() if len(sections) > 1 else ""
        result = {"interfaces": addr, "listening_ports": ports}
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


# ── Процессы ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def pi_process_list(sort_by: str = "cpu") -> str:
    """
    Топ-20 процессов на Pi.

    sort_by: 'cpu' или 'mem'
    """
    err = _check_config()
    if err:
        return err
    try:
        field = "3" if sort_by == "cpu" else "4"
        cmd = f"ps aux --sort=-{field} | head -21"
        return await _run(cmd)
    except Exception as e:
        return f"Ошибка: {e}"


# ── Файловая система ──────────────────────────────────────────────────────────

@mcp.tool()
async def pi_list_dir(path: str) -> str:
    """
    Список файлов и директорий на Pi.

    path: путь к директории (например '~' или '/home/vk/homeassistant')
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"ls -la {path}")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_read_file(path: str) -> str:
    """
    Прочитать содержимое файла на Pi.

    path: путь к файлу (например '/etc/hostname')
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"cat {path}")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_write_file(path: str, content: str) -> str:
    """
    Записать/перезаписать файл на Pi через SFTP.

    path: путь к файлу на Pi
    content: содержимое файла
    """
    err = _check_config()
    if err:
        return err
    try:
        async with asyncssh.connect(**_conn_kwargs()) as conn:
            async with conn.start_sftp_client() as sftp:
                path = await _sftp_resolve(sftp, path)
                async with await sftp.open(path, "w") as f:
                    await f.write(content)
        return f"✓ Файл записан: {path}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_upload_file(local_path: str, remote_path: str) -> str:
    """
    Загрузить файл с Windows на Pi по SFTP.

    local_path: путь к файлу на Windows (например 'C:/Users/vladi/Downloads/bg.jpg')
    remote_path: путь назначения на Pi (например '~/homeassistant/www/bg.jpg')
    """
    err = _check_config()
    if err:
        return err
    try:
        local = Path(local_path)
        if not local.exists():
            return f"Ошибка: локальный файл не найден: {local_path}"
        async with asyncssh.connect(**_conn_kwargs()) as conn:
            async with conn.start_sftp_client() as sftp:
                remote_path = await _sftp_resolve(sftp, remote_path)
                await sftp.put(str(local), remote_path)
        size = local.stat().st_size
        return f"✓ Загружен {local.name} ({size // 1024} KB) → {remote_path}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_mkdir(path: str) -> str:
    """
    Создать директорию на Pi (включая все промежуточные).

    path: путь к директории (например '/DATA/AppData/ideahunter/data')
    """
    err = _check_config()
    if err:
        return err
    try:
        await _run(f"mkdir -p {path}")
        return f"✓ Директория создана: {path}"
    except Exception as e:
        return f"Ошибка: {e}"


# Папки/файлы исключаемые при рекурсивной загрузке
_UPLOAD_EXCLUDE = {".env", "data", "logs", "__pycache__", ".git", ".venv", ".mypy_cache", ".pytest_cache"}
_UPLOAD_EXCLUDE_EXT = {".pyc", ".pyo"}


@mcp.tool()
async def pi_upload_dir(local_path: str, remote_path: str) -> str:
    """
    Загрузить папку с Windows на Pi по SFTP (рекурсивно).
    Автоматически пропускает: .env, data/, logs/, __pycache__/, .git/, .venv/, *.pyc

    local_path: путь к папке на Windows (например 'C:/Users/vladi/Projects/ideahunter')
    remote_path: путь назначения на Pi (например '~/bots/ideahunter')
    """
    err = _check_config()
    if err:
        return err
    try:
        local = Path(local_path)
        if not local.exists() or not local.is_dir():
            return f"Ошибка: папка не найдена: {local_path}"

        # Собираем (local_file, relative_posix_path)
        files_to_upload: list[tuple[Path, str]] = []
        for root, dirs, files in os.walk(local):
            root_path = Path(root)
            # Фильтруем исключённые папки (in-place, чтобы os.walk не заходил в них)
            dirs[:] = [d for d in dirs if d not in _UPLOAD_EXCLUDE]
            for fname in files:
                if fname in _UPLOAD_EXCLUDE or Path(fname).suffix in _UPLOAD_EXCLUDE_EXT:
                    continue
                local_file = root_path / fname
                rel = local_file.relative_to(local)
                files_to_upload.append((local_file, rel.as_posix()))

        if not files_to_upload:
            return "Нет файлов для загрузки"

        async with asyncssh.connect(**_conn_kwargs()) as conn:
            async with conn.start_sftp_client() as sftp:
                # Раскрываем ~ после подключения через realpath
                resolved = await _sftp_resolve(sftp, remote_path)
                for local_file, rel_posix in files_to_upload:
                    remote_file = f"{resolved}/{rel_posix}"
                    remote_dir = "/".join(remote_file.split("/")[:-1])
                    await sftp.makedirs(remote_dir, exist_ok=True)
                    await sftp.put(str(local_file), remote_file)

        total_size = sum(f.stat().st_size for f, _ in files_to_upload) // 1024
        return f"✓ Загружено {len(files_to_upload)} файлов ({total_size} KB) → {resolved}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_download_file(remote_path: str, local_path: str) -> str:
    """
    Скачать файл с Pi на Windows по SFTP.

    remote_path: путь к файлу на Pi
    local_path: путь назначения на Windows (например 'C:/Users/vladi/Downloads/file.txt')
    """
    err = _check_config()
    if err:
        return err
    try:
        async with asyncssh.connect(**_conn_kwargs()) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, local_path)
        size = Path(local_path).stat().st_size
        return f"✓ Скачан {remote_path} → {local_path} ({size // 1024} KB)"
    except Exception as e:
        return f"Ошибка: {e}"


# ── Docker ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def pi_docker_list(all: bool = False) -> str:
    """
    Список Docker контейнеров на Pi.

    all: True — показать все (включая остановленные), False — только запущенные
    """
    err = _check_config()
    if err:
        return err
    try:
        flag = "-a" if all else ""
        return await _run(f"sudo docker ps {flag} --format 'table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_start(container: str) -> str:
    """
    Запустить Docker контейнер на Pi.

    container: имя или ID контейнера
    """
    err = _check_config()
    if err:
        return err
    try:
        result = await _run(f"sudo docker start {shlex.quote(container)}")
        return f"✓ Контейнер запущен: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_stop(container: str) -> str:
    """
    Остановить Docker контейнер на Pi.

    container: имя или ID контейнера
    """
    err = _check_config()
    if err:
        return err
    try:
        result = await _run(f"sudo docker stop {shlex.quote(container)}")
        return f"✓ Контейнер остановлен: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_restart(container: str) -> str:
    """
    Перезапустить Docker контейнер на Pi.

    container: имя или ID контейнера
    """
    err = _check_config()
    if err:
        return err
    try:
        result = await _run(f"sudo docker restart {shlex.quote(container)}")
        return f"✓ Контейнер перезапущен: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_logs(container: str, lines: int = 50) -> str:
    """
    Логи Docker контейнера на Pi.

    container: имя или ID контейнера
    lines: количество последних строк (по умолчанию 50)
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"sudo docker logs --tail {int(lines)} {shlex.quote(container)} 2>&1")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_remove(container: str) -> str:
    """
    Удалить Docker контейнер на Pi (только остановленный).

    container: имя или ID контейнера
    """
    err = _check_config()
    if err:
        return err
    try:
        result = await _run(f"sudo docker rm {shlex.quote(container)}")
        return f"✓ Контейнер удалён: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_docker_run(
    image: str,
    name: str,
    ports: str = "",
    volumes: str = "",
    env_vars: str = "",
) -> str:
    """
    Создать и запустить новый Docker контейнер на Pi.

    image: образ (например 'nginx:latest')
    name: имя контейнера
    ports: проброс портов (например '8080:80' или '8080:80,443:443')
    volumes: монтирование томов (например '/data:/app/data')
    env_vars: переменные окружения (например 'KEY=val,OTHER=val2')
    """
    err = _check_config()
    if err:
        return err
    try:
        cmd = f"sudo docker run -d --name {name} --restart unless-stopped"
        for p in ports.split(","):
            p = p.strip()
            if p:
                cmd += f" -p {p}"
        for v in volumes.split(","):
            v = v.strip()
            if v:
                cmd += f" -v {v}"
        for e in env_vars.split(","):
            e = e.strip()
            if e:
                cmd += f" -e {e}"
        cmd += f" {image}"
        result = await _run(cmd)
        return f"✓ Контейнер запущен: {result}"
    except Exception as e:
        return f"Ошибка: {e}"


# ── Docker Compose ────────────────────────────────────────────────────────────

@mcp.tool()
async def pi_compose_ps(project_path: str) -> str:
    """
    Статус сервисов Docker Compose на Pi.

    project_path: путь к директории с docker-compose.yml (например '~/homeassistant')
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"cd {shlex.quote(project_path)} && sudo docker compose ps")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_compose_up(project_path: str, detach: bool = True, build: bool = False) -> str:
    """
    Поднять сервисы Docker Compose на Pi.

    project_path: путь к директории с docker-compose.yml
    detach: True — запустить в фоне (рекомендуется)
    build: True — пересобрать образы перед запуском (--build)
    """
    err = _check_config()
    if err:
        return err
    try:
        flags = []
        if detach:
            flags.append("-d")
        if build:
            flags.append("--build")
        flag_str = " ".join(flags)
        return await _run(f"cd {shlex.quote(project_path)} && sudo docker compose up {flag_str} 2>&1")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_compose_down(project_path: str) -> str:
    """
    Остановить и удалить сервисы Docker Compose на Pi.

    project_path: путь к директории с docker-compose.yml
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"cd {shlex.quote(project_path)} && sudo docker compose down 2>&1")
    except Exception as e:
        return f"Ошибка: {e}"


# ── Systemd сервисы ───────────────────────────────────────────────────────────

@mcp.tool()
async def pi_service_status(service: str) -> str:
    """
    Статус systemd сервиса на Pi.

    service: имя сервиса (например 'homeassistant', 'nginx', 'docker')
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"sudo systemctl status {shlex.quote(service)} --no-pager -l")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_service_start(service: str) -> str:
    """
    Запустить systemd сервис на Pi.

    service: имя сервиса
    """
    err = _check_config()
    if err:
        return err
    try:
        await _run(f"sudo systemctl start {shlex.quote(service)}")
        return f"✓ Сервис запущен: {service}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_service_stop(service: str) -> str:
    """
    Остановить systemd сервис на Pi.

    service: имя сервиса
    """
    err = _check_config()
    if err:
        return err
    try:
        await _run(f"sudo systemctl stop {shlex.quote(service)}")
        return f"✓ Сервис остановлен: {service}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_service_restart(service: str) -> str:
    """
    Перезапустить systemd сервис на Pi.

    service: имя сервиса
    """
    err = _check_config()
    if err:
        return err
    try:
        await _run(f"sudo systemctl restart {shlex.quote(service)}")
        return f"✓ Сервис перезапущен: {service}"
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_service_logs(service: str, lines: int = 50) -> str:
    """
    Логи systemd сервиса на Pi (journalctl).

    service: имя сервиса
    lines: количество последних строк (по умолчанию 50)
    """
    err = _check_config()
    if err:
        return err
    try:
        return await _run(f"sudo journalctl -u {shlex.quote(service)} -n {int(lines)} --no-pager")
    except Exception as e:
        return f"Ошибка: {e}"


@mcp.tool()
async def pi_run(command: str, sudo: bool = False) -> str:
    """
    Выполнить произвольную команду на Pi через SSH.

    command: bash-команда для выполнения
    sudo: True — выполнить с sudo (для apt, записи в /etc/ и т.д.)
    """
    err = _check_config()
    if err:
        return err
    try:
        cmd = f"sudo {command}" if sudo else command
        return await _run(cmd)
    except Exception as e:
        return f"Ошибка: {e}"


if __name__ == "__main__":
    mcp.run()
