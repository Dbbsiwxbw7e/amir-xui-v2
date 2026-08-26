"""Multi-account Railway tokens — persistent JSON."""
import json
import logging
import os
import threading

log = logging.getLogger(__name__)


class Accounts:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.d = {"accs": {}, "active": {}}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path) as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self.d.update(raw)
        except Exception as e:
            log.warning("load accounts failed: %s", e)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path + ".tmp", "w") as f:
                json.dump(self.d, f)
            os.replace(self.path + ".tmp", self.path)
        except Exception as e:
            log.warning("⚠️ SAVE FAILED (%s) — بدون Volume اکانت‌ها بعد از ری‌استارت پاک می‌شوند!", e)

    def add(self, uid, label, token, email=""):
        with self.lock:
            accs = self.d["accs"].setdefault(str(uid), {})
            if label in accs:
                return False
            accs[label] = {"token": token, "email": email}
            self.d["active"][str(uid)] = label   # new account always becomes active
            self._save()
        return True

    def remove(self, uid, label):
        with self.lock:
            accs = self.d["accs"].get(str(uid), {})
            if label not in accs:
                return False
            del accs[label]
            if self.d["active"].get(str(uid)) == label:
                rest = list(accs)
                if rest:
                    self.d["active"][str(uid)] = rest[0]
                else:
                    self.d["active"].pop(str(uid), None)
            self._save()
        return True

    def get(self, uid):
        with self.lock:
            lbl = self.d["active"].get(str(uid))
            e = self.d["accs"].get(str(uid), {}).get(lbl or "")
            return (dict(e), lbl) if e else (None, "")

    def list(self, uid):
        with self.lock:
            accs = self.d["accs"].get(str(uid), {})
            act = self.d["active"].get(str(uid))
            return [{"label": k, "email": v.get("email", ""), "active": k == act}
                    for k, v in accs.items()]

    def switch(self, uid, label):
        with self.lock:
            if label not in self.d["accs"].get(str(uid), {}):
                return False
            self.d["active"][str(uid)] = label
            self._save()
        return True

    def active_label(self, uid):
        with self.lock:
            return self.d["active"].get(str(uid), "")
