"""
Multi-account Railway tokens, persistent.
"""
import json, os, threading

PATH = os.getenv("ACCOUNTS_FILE", "/data/accounts.json")


class Accounts:
    def __init__(self, path=PATH):
        self.path = path
        self._lock = threading.Lock()
        self._d = {"accounts": {}, "active": {}}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path) as f:
                    raw = json.load(f)
                if isinstance(raw, dict): self._d.update(raw)
        except Exception: pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path + ".tmp", "w") as f: json.dump(self._d, f)
            os.replace(self.path + ".tmp", self.path)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "ذخیره اکانت‌ها ناموفق (%s) — بدون Volume روی /data اکانت‌ها بعد از ری‌استارت پاک می‌شوند!", e)

    def add(self, uid, label, token, email=""):
        with self._lock:
            accs = self._d["accounts"].setdefault(str(uid), {})
            if label in accs: return False
            accs[label] = {"token": token, "email": email}
            self._d["active"].setdefault(str(uid), label)
            self._save()
        return True

    def remove(self, uid, label):
        with self._lock:
            accs = self._d["accounts"].get(str(uid), {})
            if label not in accs: return False
            del accs[label]
            if self._d["active"].get(str(uid)) == label:
                rest = list(accs.keys())
                if rest: self._d["active"][str(uid)] = rest[0]
                else: self._d["active"].pop(str(uid), None)
            self._save()
        return True

    def get(self, uid, label=None):
        with self._lock:
            lbl = label or self._d["active"].get(str(uid))
            e = self._d["accounts"].get(str(uid), {}).get(lbl or "")
            return dict(e) if e else None

    def list(self, uid):
        with self._lock:
            accs = self._d["accounts"].get(str(uid), {})
            act = self._d["active"].get(str(uid))
            return [{"label": k, "email": v.get("email",""), "active": k==act}
                    for k,v in accs.items()]

    def set_active(self, uid, label):
        with self._lock:
            if label not in self._d["accounts"].get(str(uid), {}): return False
            self._d["active"][str(uid)] = label
            self._save()
        return True

    def active_label(self, uid):
        with self._lock: return self._d["active"].get(str(uid), "")

    def labels(self, uid):
        with self._lock: return list(self._d["accounts"].get(str(uid), {}).keys())
