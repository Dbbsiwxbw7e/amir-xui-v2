"""
Railway GraphQL client — requests-based, exception-based, UA set.
"""
import requests

API_URL = "https://api.railway.app/graphql/v2"


class RailwayError(Exception):
    pass


class RailwayAPI:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "railway-cli/5.30.4",
            "Accept": "*/*",
        }

    def gql(self, query: str, variables: dict | None = None) -> dict:
        try:
            r = requests.post(API_URL,
                              json={"query": query, "variables": variables or {}},
                              headers=self.headers, timeout=30)
        except requests.RequestException as e:
            raise RailwayError(f"خطای شبکه: {e}") from e
        if r.status_code == 401:
            raise RailwayError("توکن Railway نامعتبره.")
        if r.status_code != 200:
            body = r.text[:300]
            if "Problem processing request" in body:
                raise RailwayError(
                    "🚫 Railway اجازه ساخت منبع جدید نمیده. دلایل رایج:\n"
                    "     • سقف Free plan پر شده (حذف پروژه‌های قدیمی)\n"
                    "     • اکانت جدید بدون کارت تأییدشده\n"
                    "     • محدودیت نرخ: هر ۳۰ ثانیه یک پروژه — چند لحظه بعد دوباره امتحان کن\n\n"
                    f"جزئیات فنی: {body}")
            if "limit exceeded" in body:
                raise RailwayError("🚫 سقف Free plan پر شده — پروژه‌های قدیمی رو حذف کن.")
            raise RailwayError(f"HTTP {r.status_code}: {body}")
        data = r.json()
        if data.get("errors"):
            msg = "; ".join(e.get("message", "?") for e in data["errors"])
            if "Problem processing request" in msg or "limit exceeded" in msg:
                msg += ("\n💡 احتمالاً سقف Free plan پر شده — چند پروژه قدیمی رو "
                        "از داشبورد Railway حذف کن یا اکانت جدید بساز.")
            raise RailwayError(msg)
        return data.get("data", {})

    # ── account ──
    def whoami(self):
        d = self.gql("{ me { email workspaces { id } } }")
        me = d.get("me") or {}
        ws = (me.get("workspaces") or [{}])[0].get("id", "")
        return ws, me.get("email", "")

    # ── projects ──
    def create_project(self, name, workspace_id):
        d = self.gql("""mutation($i: ProjectCreateInput!){
            projectCreate(input:$i){ id name }}""",
            {"input": {"name": name, "workspaceId": workspace_id}})
        p = d.get("projectCreate")
        if not p: raise RailwayError("ساخت پروژه شکست خورد")
        return p

    def list_projects(self):
        d = self.gql("""{me{workspaces{projects(first:50){edges{node{id name createdAt}}}}}}""")
        out = []
        for ws in (d.get("me") or {}).get("workspaces", []):
            out += [e["node"] for e in ws["projects"]["edges"]]
        return out

    def delete_project(self, pid):
        return bool(self.gql("mutation($id:String!){projectDelete(id:$id)}",
                             {"id": pid}).get("projectDelete"))

    def get_environments(self, project_id):
        d = self.gql("""query($p:String!){environments(projectId:$p){
            edges{node{id name}}}}""", {"p": project_id})
        edges = (d.get("environments") or {}).get("edges") or []
        return [e["node"] for e in edges]

    # ── services ──
    def create_service(self, name, project_id, image):
        d = self.gql("""mutation($i: ServiceCreateInput!){
            serviceCreate(input:$i){ id name }}""",
            {"input": {"projectId": project_id, "name": name,
                       "source": {"image": image}}})
        s = d.get("serviceCreate")
        if not s: raise RailwayError(f"ساخت سرویس {name} شکست خورد")
        return s

    def deploy(self, service_id, environment_id):
        self.gql("""mutation($s:String!,$e:String!){
            serviceInstanceDeploy(serviceId:$s,environmentId:$e)}""",
            {"serviceId": service_id, "environmentId": environment_id})

    def create_domain(self, service_id, environment_id, target_port):
        d = self.gql("""mutation($i: ServiceDomainCreateInput!){
            serviceDomainCreate(input:$i){ domain }}""",
            {"input": {"serviceId": service_id, "environmentId": environment_id,
                       "targetPort": target_port}})
        return (d.get("serviceDomainCreate") or {}).get("domain", "")

    def latest_deployment(self, service_id):
        d = self.gql("""query($id:String!){service(id:$id){
            deployments(last:1){edges{node{id status staticUrl}}}}}""",
            {"id": service_id})
        edges = ((d.get("service") or {}).get("deployments") or {}).get("edges") or []
        return edges[-1]["node"] if edges else None
