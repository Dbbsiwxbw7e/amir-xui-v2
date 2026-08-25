"""
3x-ui panel client — ws+tls inbound (amir_xu spec) + node management.
"""
import json
import re
import urllib.parse

import requests


class XUIError(Exception):
    pass


class PanelClient:
    def __init__(self, base_url, username, password):
        self.base = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.s = requests.Session()
        self.csrf = ""

    def _csrf(self):
        try:
            r = self.s.get(f"{self.base}/managepanel/", timeout=15)
            m = re.search(r'csrf-token.*?content="([^"]+)"', r.text)
            if m: self.csrf = m.group(1)
        except requests.RequestException:
            pass

    def _req(self, method, path, payload=None):
        url = f"{self.base}/managepanel{path}"
        try:
            if method == "GET":
                r = self.s.get(url, headers={"X-CSRF-Token": self.csrf}, timeout=20)
            else:
                r = self.s.post(url, json=payload or {},
                                headers={"X-CSRF-Token": self.csrf}, timeout=30)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            raise XUIError(f"{path}: {e}") from e

    def login(self):
        self._csrf()
        d = self._req("POST", "/login",
                      {"username": self.username, "password": self.password})
        if d.get("success"):
            self._csrf()
            return True
        return False

    # ── ws+tls inbound (exact amir_xu spec) ──
    def create_ws_tls_inbound(self, uuid, email, domain, port, path):
        stream = {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "serverName": domain,
                "alpn": ["http/1.1"],
                "certificates": [],
                "allowInsecure": False,
            },
            "wsSettings": {"path": path, "headers": {"Host": domain}},
        }
        data = {
            "up": 0, "down": 0, "total": 0,
            "remark": f"WS-TLS-{email}",
            "enable": True, "expiryTime": 0, "listen": "",
            "port": port, "protocol": "vless",
            "settings": json.dumps({
                "clients": [{
                    "id": uuid, "flow": "", "email": email,
                    "limitIp": 0, "totalGB": 0, "expiredTime": 0,
                    "enable": True, "tgId": 0, "subId": "",
                }],
                "decryption": "none", "fallbacks": [],
            }),
            "streamSettings": json.dumps(stream),
            "sniffing": json.dumps({"enabled": False, "destOverride": [], "routeOnly": False}),
            "tag": f"vless-ws-{email}", "listenning": "",
        }
        return self._req("POST", "/panel/api/inbounds/add", data)

    def list_inbounds(self):
        return (self._req("GET", "/panel/api/inbounds/list").get("obj") or [])

    def delete_inbound(self, inbound_id):
        return self._req("POST", f"/panel/api/inbounds/del/{inbound_id}")

    # ── nodes ──
    def get_uuid(self):
        d = self._req("GET", "/panel/api/server/getNewUUID")
        return (d.get("obj") or {}).get("uuid", "")

    def create_api_token(self, name="node-token"):
        toks = self._req("GET", "/panel/api/setting/apiTokens")
        for t in (toks.get("obj") or []):
            try: self._req("POST", f"/panel/api/setting/apiTokens/delete/{t['id']}")
            except XUIError: pass
        d = self._req("POST", "/panel/api/setting/apiTokens/create", {"name": name})
        return (d.get("obj") or {}).get("token", "")

    def add_node(self, node_name, node_url, node_uuid, node_token):
        host = node_url.replace("https://","").replace("http://","").rstrip("/")
        return self._req("POST", "/panel/api/nodes/add", {
            "name": node_name, "address": host, "port": 443, "scheme": "https",
            "serialNumber": node_uuid, "apiToken": node_token,
            "trafficLimit": 0, "weight": 100, "remark": f"{node_name} Node",
            "checkInterval": 60, "checkType": "http", "notify": True,
            "alertThreshold": 0, "enable": True, "allowPrivateAddress": False,
            "basePath": "/managepanel/", "inboundSyncMode": "all",
            "inboundTags": [], "outboundTag": "", "pinnedCertSha256": "",
            "tlsVerifyMode": "skip",
        })


def build_vless_link(domain, uuid, path="/cdn", name="config"):
    host = domain.replace("https://","").replace("http://","").rstrip("/")
    q = urllib.parse.quote(path, safe="")
    n = urllib.parse.quote(name)
    return (f"vless://{uuid}@{host}:443?encryption=none&security=tls"
            f"&sni={host}&fp=chrome&type=ws&host={host}&path={q}#{n}")


def wait_ready(base_url, timeout=90, interval=5):
    import time
    probe = base_url.rstrip("/") + "/managepanel/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(probe, timeout=10).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False
