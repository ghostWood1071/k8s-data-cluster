#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

KEYCLOAK_URL="${KEYCLOAK_URL:-https://keycloak.datalabutehy.com}"
KEYCLOAK_ADMIN_REALM="${KEYCLOAK_ADMIN_REALM:-master}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-data-team}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER:-temp-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-ddddf6aac8c14a6fbc011b1a74482b1a}"
RANCHER_URL="${RANCHER_URL:-https://rancher.datalabutehy.com}"
RANCHER_CLIENT_ID="${RANCHER_CLIENT_ID:-rancher}"
RANCHER_ADMIN_EMAIL="${RANCHER_ADMIN_EMAIL:-letritung2302@gmail.com}"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required"; exit 1; }

tmp_secret="$(mktemp)"
cleanup() {
  rm -f "$tmp_secret" /tmp/rancher-keycloak-authconfig.yaml
}
trap cleanup EXIT

KEYCLOAK_URL="$KEYCLOAK_URL" \
KEYCLOAK_ADMIN_REALM="$KEYCLOAK_ADMIN_REALM" \
KEYCLOAK_REALM="$KEYCLOAK_REALM" \
KEYCLOAK_ADMIN_USER="$KEYCLOAK_ADMIN_USER" \
KEYCLOAK_ADMIN_PASSWORD="$KEYCLOAK_ADMIN_PASSWORD" \
RANCHER_URL="$RANCHER_URL" \
RANCHER_CLIENT_ID="$RANCHER_CLIENT_ID" \
RANCHER_ADMIN_EMAIL="$RANCHER_ADMIN_EMAIL" \
CLIENT_SECRET_FILE="$tmp_secret" \
python3 <<'PY'
import json
import os
import urllib.error
import urllib.parse
import urllib.request

KEYCLOAK_URL = os.environ["KEYCLOAK_URL"].rstrip("/")
ADMIN_REALM = os.environ["KEYCLOAK_ADMIN_REALM"]
REALM = os.environ["KEYCLOAK_REALM"]
ADMIN_USER = os.environ["KEYCLOAK_ADMIN_USER"]
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
RANCHER_URL = os.environ["RANCHER_URL"].rstrip("/")
CLIENT_ID = os.environ["RANCHER_CLIENT_ID"]
ADMIN_EMAIL = os.environ["RANCHER_ADMIN_EMAIL"].lower()
SECRET_FILE = os.environ["CLIENT_SECRET_FILE"]

ROLES = {
    "rancher-admin": "Rancher global administrator",
    "rancher-user": "Rancher standard user",
    "rancher-cluster-owner": "Rancher local cluster owner",
}
GROUP_ROLE_MAP = {
    "rancher-admins": ["rancher-admin"],
    "rancher-users": ["rancher-user"],
    "rancher-cluster-owners": ["rancher-cluster-owner"],
}
ADMIN_GROUPS = ["rancher-admins", "rancher-cluster-owners"]
ADMIN_ROLES = ["rancher-admin", "rancher-cluster-owner"]

def req(method, path, data=None, token=None, form=False):
    headers = {"User-Agent": "rancher-keycloak-deploy"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    request = urllib.request.Request(KEYCLOAK_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            text = response.read().decode()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} HTTP {exc.code}: {text[:1200]}") from exc

token = req(
    "POST",
    f"/realms/{ADMIN_REALM}/protocol/openid-connect/token",
    form=True,
    data={
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASSWORD,
    },
)["access_token"]

client_payload = {
    "clientId": CLIENT_ID,
    "name": "Rancher",
    "protocol": "openid-connect",
    "publicClient": False,
    "standardFlowEnabled": True,
    "directAccessGrantsEnabled": False,
    "serviceAccountsEnabled": False,
    "redirectUris": [f"{RANCHER_URL}/verify-auth"],
    "webOrigins": [RANCHER_URL],
    "attributes": {"pkce.code.challenge.method": ""},
}
clients = req("GET", f"/admin/realms/{REALM}/clients?{urllib.parse.urlencode({'clientId': CLIENT_ID})}", token=token) or []
if clients:
    client_uuid = clients[0]["id"]
    existing = req("GET", f"/admin/realms/{REALM}/clients/{client_uuid}", token=token)
    existing.update(client_payload)
    attrs = {k: v for k, v in (existing.get("attributes") or {}).items() if "pkce" not in k.lower() and "code.challenge" not in k.lower()}
    attrs["pkce.code.challenge.method"] = ""
    existing["attributes"] = attrs
    req("PUT", f"/admin/realms/{REALM}/clients/{client_uuid}", token=token, data=existing)
else:
    req("POST", f"/admin/realms/{REALM}/clients", token=token, data=client_payload)
    client_uuid = req("GET", f"/admin/realms/{REALM}/clients?{urllib.parse.urlencode({'clientId': CLIENT_ID})}", token=token)[0]["id"]

mappers = req("GET", f"/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models", token=token) or []
if not any(m.get("name") == "groups" for m in mappers):
    req(
        "POST",
        f"/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models",
        token=token,
        data={
            "name": "groups",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-group-membership-mapper",
            "consentRequired": False,
            "config": {
                "full.path": "false",
                "claim.name": "groups",
                "jsonType.label": "String",
                "multivalued": "true",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        },
    )

existing_roles = {r["name"]: r for r in (req("GET", f"/admin/realms/{REALM}/clients/{client_uuid}/roles", token=token) or [])}
for role_name, description in ROLES.items():
    if role_name not in existing_roles:
        req("POST", f"/admin/realms/{REALM}/clients/{client_uuid}/roles", token=token, data={"name": role_name, "description": description})
role_reps = {r["name"]: r for r in (req("GET", f"/admin/realms/{REALM}/clients/{client_uuid}/roles", token=token) or [])}

groups = req("GET", f"/admin/realms/{REALM}/groups?max=200", token=token) or []
groups_by_name = {g["name"]: g for g in groups}
for group_name in GROUP_ROLE_MAP:
    if group_name not in groups_by_name:
        req("POST", f"/admin/realms/{REALM}/groups", token=token, data={"name": group_name})
groups = req("GET", f"/admin/realms/{REALM}/groups?max=200", token=token) or []
groups_by_name = {g["name"]: g for g in groups}

for group_name, role_names in GROUP_ROLE_MAP.items():
    group_id = groups_by_name[group_name]["id"]
    mapped = req("GET", f"/admin/realms/{REALM}/groups/{group_id}/role-mappings/clients/{client_uuid}", token=token) or []
    mapped_names = {r["name"] for r in mapped}
    missing = [role_reps[name] for name in role_names if name not in mapped_names]
    if missing:
        req("POST", f"/admin/realms/{REALM}/groups/{group_id}/role-mappings/clients/{client_uuid}", token=token, data=missing)

users = req("GET", f"/admin/realms/{REALM}/users?{urllib.parse.urlencode({'search': ADMIN_EMAIL, 'max': '20'})}", token=token) or []
user = next((u for u in users if (u.get("email") or "").lower() == ADMIN_EMAIL or (u.get("username") or "").lower() == ADMIN_EMAIL), None)
if user:
    user_id = user["id"]
    current_groups = req("GET", f"/admin/realms/{REALM}/users/{user_id}/groups?max=200", token=token) or []
    current_group_names = {g["name"] for g in current_groups}
    for group_name in ADMIN_GROUPS:
        if group_name not in current_group_names:
            req("PUT", f"/admin/realms/{REALM}/users/{user_id}/groups/{groups_by_name[group_name]['id']}", token=token)
    current_roles = req("GET", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/clients/{client_uuid}", token=token) or []
    current_role_names = {r["name"] for r in current_roles}
    missing = [role_reps[name] for name in ADMIN_ROLES if name not in current_role_names]
    if missing:
        req("POST", f"/admin/realms/{REALM}/users/{user_id}/role-mappings/clients/{client_uuid}", token=token, data=missing)

secret = req("GET", f"/admin/realms/{REALM}/clients/{client_uuid}/client-secret", token=token)["value"]
open(SECRET_FILE, "w", encoding="utf-8").write(secret)

print(f"Keycloak client ready: realm={REALM}, client={CLIENT_ID}")
print("Groups ready: " + ", ".join(GROUP_ROLE_MAP))
if user:
    print(f"Admin user mapped: {ADMIN_EMAIL}")
else:
    print(f"Admin user not found, skipped user mapping: {ADMIN_EMAIL}")
PY

client_secret="$(cat "$tmp_secret")"
issuer="${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}"

cat > /tmp/rancher-keycloak-authconfig.yaml <<YAML
apiVersion: management.cattle.io/v3
kind: AuthConfig
metadata:
  name: keycloakoidc
type: keyCloakOIDCConfig
enabled: true
accessMode: unrestricted
allowedPrincipalIds: []
clientId: ${RANCHER_CLIENT_ID}
clientSecret: "${client_secret}"
rancherUrl: ${RANCHER_URL}/verify-auth
issuer: ${issuer}
authEndpoint: ${issuer}/protocol/openid-connect/auth
tokenEndpoint: ${issuer}/protocol/openid-connect/token
userInfoEndpoint: ${issuer}/protocol/openid-connect/userinfo
jwksUrl: ${issuer}/protocol/openid-connect/certs
scopes: "openid profile email"
displayNameField: name
groupsField: groups
uidField: sub
userNameField: preferred_username
YAML

kubectl apply -f /tmp/rancher-keycloak-authconfig.yaml
kubectl apply -f "${SCRIPT_DIR}/rancher-keycloak-rbac.yaml"

echo "Rancher OIDC deployed."
echo "Login URL: ${RANCHER_URL}"
echo "OIDC realm: ${KEYCLOAK_REALM}"