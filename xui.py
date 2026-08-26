"""
3x-ui panel client — ws+tls inbounds (amir_xu spec), nodes, vless links.
Sync; raise PanelError on failure.
"""
import json
import re
import time
import urllib.parse

import requests

import config
from errors import PanelError


class Panel:
    def __init__(self, url: str):
        self.base = url.rstrip("/")
        self.s = requests.Session()
        self.csrf = ""

    # ── low level ──
    def _csrf(self):
        try:
            r = self.s.get(f"{self.base}/managepanel/", timeout=15)
            m = re.search(r'csrf-token.*?content="([^"]+)"', r.text)
            if m:
                self.csrf = m.group(1)
        except requests.RequestException:
            pass

    def _call(self, method, path, payload=None):
        url = f"{self.base}/managepanel{path}"
        h = {"X-CSRF-Token": self.csrf}
        try:
            if method == "GET":
                r = self.s.get(url, headers=h, timeout=20)
            else:
                r = self.s.post(url, json=payload or {}, headers=h, timeout=30)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            raise PanelError(f"{path}: {e}") from e

    def login(self) -> bool:
        self._csrf()
        d = self._call("POST", "/login",
                       {"username": config.XUI_USER, "password": config.XUI_PASS})
        ok = bool(d.get("success"))
        if ok:
            self._csrf()
        return ok

    # ── ws+tls inbound (amir_xu spec) ──
    def create_ws_tls_inbound(self, uuid, email, domain, port, path):
        # NOTE: TLS is terminated at Railway's edge. The inbound itself must be
        # plain ws (security=none), otherwise Xray has no cert and handshakes fail.
        stream = {
            "network": "ws",
            "security": "none",
            "wsSettings": {"path": path, "headers": {"Host": domain}},
        }
        return self._call("POST", "/panel/api/inbounds/add", {
            "up": 0, "down": 0, "total": 0,
            "remark": f"WS-TLS-{email}", "enable": True,
            "expiryTime": 0, "listen": "", "port": port, "protocol": "vless",
            "settings": json.dumps({"clients": [{
                "id": uuid, "flow": "", "email": email, "limitIp": 0,
                "totalGB": 0, "expiredTime": 0, "enable": True,
                "tgId": 0, "subId": ""}], "decryption": "none", "fallbacks": []}),
            "streamSettings": json.dumps(stream),
            "sniffing": json.dumps({"enabled": False, "destOverride": [],
                                    "routeOnly": False}),
            "tag": f"vless-ws-{email}", "listenning": "",
        })

    def inbounds(self) -> list:
        return (self._call("GET", "/panel/api/inbounds/list").get("obj") or [])

    def delete_inbound(self, iid):
        return self._call("POST", f"/panel/api/inbounds/del/{iid}")

    # ── nodes ──
    def node_uuid(self) -> str:
        d = self._call("GET", "/panel/api/server/getNewUUID")
        return (d.get("obj") or {}).get("uuid", "")

    def node_token(self, name="node-token") -> str:
        toks = self._call("GET", "/panel/api/setting/apiTokens")
        for t in (toks.get("obj") or []):
            try:
                self._call("POST", f"/panel/api/setting/apiTokens/delete/{t['id']}")
            except PanelError:
                pass
        d = self._call("POST", "/panel/api/setting/apiTokens/create", {"name": name})
        return (d.get("obj") or {}).get("token", "")

    def add_node(self, name, url, nuuid, ntoken):
        host = url.replace("https://", "").replace("http://", "").rstrip("/")
        return self._call("POST", "/panel/api/nodes/add", {
            "name": name, "address": host, "port": 443, "scheme": "https",
            "serialNumber": nuuid, "apiToken": ntoken, "trafficLimit": 0,
            "weight": 100, "remark": f"{name} Node", "checkInterval": 60,
            "checkType": "http", "notify": True, "alertThreshold": 0,
            "enable": True, "allowPrivateAddress": False,
            "basePath": "/managepanel/", "inboundSyncMode": "all",
            "inboundTags": [], "outboundTag": "", "pinnedCertSha256": "",
            "tlsVerifyMode": "skip"})


def vless_link(domain, uid, path="/cdn", name="cfg"):
    h = domain.replace("https://", "").replace("http://", "").rstrip("/")
    p = urllib.parse.quote(path, safe="")
    return (f"vless://{uid}@{h}:443?encryption=none&security=tls"
            f"&sni={h}&fp=chrome&type=ws&host={h}&path={p}"
            f"#{urllib.parse.quote(name)}")


def wait_ready(url, timeout=90, every=5):
    probe = url.rstrip("/") + "/managepanel/"
    end = time.time() + timeout
    while time.time() < end:
        try:
            if requests.get(probe, timeout=10).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(every)
    return False
