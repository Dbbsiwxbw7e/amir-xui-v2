"""
Central configuration — env-first with sane defaults.
"""
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Railway deployment ─────────────────────────────────────────
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "ghcr.io/djsjsnsjcjx/3xui_amir:latest")
PROJECT_NAME = os.getenv("PROJECT_NAME", "amir-xui-v2")

def _parse_panels(raw: str):
    panels = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        name, _, region = item.partition(":")
        panels.append({"name": name.strip(), "region": region.strip() or name.strip()})
    return panels

PANELS = _parse_panels(os.getenv("PANELS", "NL:NL,US_V:US-VA,SG:SG,NL_MT:NL-MT"))
MAIN_PANEL = os.getenv("MAIN_PANEL", PANELS[0]["name"] if PANELS else "NL")

# 4 inbounds created per panel right after deploy
INBOUNDS_PER_PANEL = int(os.getenv("INBOUNDS_PER_PANEL", "4"))

# ── Panel credentials ──────────────────────────────────────────
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "admin")

# ── Inbound (ws+tls) defaults — same spec as amir_xu ───────────
INBOUND_PORT = int(os.getenv("INBOUND_PORT", "8080"))
INBOUND_PATH = os.getenv("INBOUND_PATH", "/cdn")

# ── Domain port (nginx entry) ──────────────────────────────────
DOMAIN_TARGET_PORT = int(os.getenv("DOMAIN_TARGET_PORT", "3000"))

# ── Timing ─────────────────────────────────────────────────────
DEPLOY_POLL_INTERVAL = 10
DEPLOY_POLL_TIMEOUT = 300
