"""Configuration — single source of truth, env-first."""
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATA_DIR = os.getenv("DATA_DIR", "/data")

# Railway
IMAGE = os.getenv("IMAGE", "ghcr.io/djsjsnsjcjx/3xui_amir:latest")
PROJECT_PREFIX = os.getenv("PROJECT_PREFIX", "amirv2")
PANELS = [p.split(":")[0].strip() for p in os.getenv(
    "PANELS", "NL,US_V,SG,NL_MT").split(",") if p.strip()]
MAIN_PANEL = os.getenv("MAIN_PANEL", PANELS[0] if PANELS else "NL")
DOMAIN_PORT = int(os.getenv("DOMAIN_PORT", "3000"))

# 3x-ui panel
XUI_USER = os.getenv("XUI_USER", "admin")
XUI_PASS = os.getenv("XUI_PASS", "admin")

# ws+tls inbound spec (identical to amir_xu)
IN_PORT = int(os.getenv("IN_PORT", "8080"))
IN_PATH = os.getenv("IN_PATH", "/cdn")
IN_PER_PANEL = int(os.getenv("IN_PER_PANEL", "4"))

# timing (seconds)
POLL_EVERY = int(os.getenv("POLL_EVERY", "10"))
POLL_MAX = int(os.getenv("POLL_MAX", "300"))
RATE_LIMIT_WAIT = 35          # railway: 1 project / 30s
