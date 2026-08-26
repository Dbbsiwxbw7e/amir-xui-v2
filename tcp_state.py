"""TCP feature state — suggested domains & per-user prefs."""
import json, os, threading

PATH = os.getenv("TCP_STATE_FILE", os.path.join(
    os.getenv("DATA_DIR", "/data"), "tcp_state.json"))
DEFAULTS = DEFAULT_GOOD_DOMAINS_STR = (
    "monorail,nozomi,turntable,trolley,reseau,autorack,metro,hopper,"
    "kodama,interchange,switchyard,junction").split(",")


class TCPState:
    def __init__(self, path=PATH):
        self.path = path
        self.lock = threading.Lock()
        self.d = {"domains": DEFAULTS, "prefs": {}}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path) as f:
                    raw = json.load(f)
                if isinstance(raw, dict): self.d.update(raw)
        except Exception: pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path + ".tmp","w") as f: json.dump(self.d,f)
            os.replace(self.path+".tmp", self.path)
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("tcp save: %s", e)

    # domains
    def domains(self): 
        with self.lock: return list(self.d["domains"])
    def add_domain(self, d):
        d = d.strip().rstrip(".")
        if not d: return False
        if not d.endswith(".proxy.rlwy.net"): d += ".proxy.rlwy.net"
        with self.lock:
            lst = self.d["domains"]
            if d in lst: return False
            lst.append(d); self._save(); return True
    def remove_domain(self, d):
        d = d.strip().rstrip(".")
        if not d.endswith(".proxy.rlwy.net"): d += ".proxy.rlwy.net"
        with self.lock:
            if d in self.d["domains"]: self.d["domains"].remove(d); self._save(); return True
            return False
    def reset_domains(self):
        with self.lock: self.d["domains"] = list(DEFAULTS); self._save()

    # per-user prefs
    def prefs(self, uid):
        with self.lock: return dict(self.d["prefs"].get(str(uid),
                                    {"count":2,"port":443,"mode":"good"}))
    def set_pref(self, uid, **kv):
        with self.lock:
            u = self.d["prefs"].setdefault(str(uid), {"count":2,"port":443,"mode":"good"})
            u.update(kv); self._save()
