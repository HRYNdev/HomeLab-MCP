# 🏠 HomeLab MCP

**Control your entire homelab with Claude AI** — Home Assistant, Docker, routers, NAS, and more.

HomeLab MCP is a collection of [Model Context Protocol](https://modelcontextprotocol.io) servers that connect Claude Desktop to your self-hosted infrastructure. Ask Claude in plain language to manage your home server, and it just works.

---

## ✨ What you can do

> *"Turn off the living room lights and start the robot vacuum"*

> *"Which Docker containers are down? Restart them."*

> *"Show me who's connected to my WiFi right now"*

> *"What's the ZFS pool health on TrueNAS?"*

> *"Are there any active alerts in Grafana?"*

---

## 🧩 Supported services

| Service | What Claude can do |
|---|---|
| **Home Assistant** | Control lights, switches, climate, vacuum; manage automations & dashboards |
| **OpenWRT** | Show connected devices, firewall rules, run commands via SSH |
| **OPNsense** | Interfaces, firewall, DHCP leases, system info |
| **MikroTik** | RouterOS REST API — interfaces, routes, system info |
| **Raspberry Pi / Linux** | SSH access, Docker containers, systemd services, file management |
| **Proxmox VE** | List/start/stop VMs and containers, node status |
| **Portainer** | Manage Docker containers, stacks, images, volumes |
| **Grafana** | Dashboards, alert rules, firing alerts, datasources |
| **TrueNAS SCALE/CORE** | ZFS pools, disks, datasets, snapshots, S.M.A.R.T., services |
| **AdGuard Home** | DNS stats, blocking toggle, custom rules |
| **Pi-hole** | DNS stats, blocking toggle |
| **Uptime Kuma** | Monitor status pages |
| **Jellyfin** | Media library, active sessions, recently added |

---

## 🚀 Quick start

### 1. Clone

```bash
git clone https://github.com/HRYNdev/HomeLab-MCP.git
cd HomeLab-MCP
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the setup wizard

```bash
python setup.py
```

The wizard will:
- Ask which services you have
- Collect credentials (URLs, tokens, passwords)
- Write `.env` with your config
- **Automatically register all servers in Claude Desktop**

Supports **English, Русский, Deutsch, Español, Français**.

### 4. Restart Claude Desktop

That's it. Claude now has full access to your homelab.

---

## 📋 Requirements

- Python 3.10+
- [Claude Desktop](https://claude.ai/download)
- Any combination of the supported services above

---

## 🔧 Manual configuration

If you prefer to configure manually, copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Then add the servers you need to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "homeassistant": {
      "command": "python",
      "args": ["/path/to/HomeLab-MCP/ha_server.py"]
    },
    "portainer": {
      "command": "python",
      "args": ["/path/to/HomeLab-MCP/portainer_server.py"]
    }
  }
}
```

Config file locations:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

---

## 🗂 Project structure

```
HomeLab-MCP/
├── setup.py               # Interactive setup wizard
├── requirements.txt        # Python dependencies
├── .env.example            # Config template
│
├── ha_server.py            # Home Assistant
├── openwrt_server.py       # OpenWRT
├── opnsense_server.py      # OPNsense
├── mikrotik_server.py      # MikroTik
├── pi_server.py            # Raspberry Pi / Linux
├── proxmox_server.py       # Proxmox VE
├── portainer_server.py     # Portainer
├── grafana_server.py       # Grafana
├── truenas_server.py       # TrueNAS
├── adguard_server.py       # AdGuard Home
├── pihole_server.py        # Pi-hole
├── uptime_kuma_server.py   # Uptime Kuma
└── jellyfin_server.py      # Jellyfin
```

---

## 🔒 Security

- All credentials are stored locally in `.env` — never sent anywhere
- `.env` is in `.gitignore` — won't be committed
- Each server reads only its own credentials
- SSH connections use `asyncssh` with proper host key handling

---

## 📄 License

MIT — do whatever you want with it.

---

## 🌟 If this helped you

Give it a star — it helps others find the project.
