import base64
import json
import ssl
import urllib.error
import urllib.request


BASE = "https://openmetadata.datalabutehy.com"
LOGIN = {"email": "admin@open-metadata.org", "password": base64.b64encode(b"admin").decode()}


def request(method, path, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "curl/8.19.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=30) as resp:
            text = resp.read().decode()
            return resp.status, text
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        return exc.code, text


status, text = request("POST", "/api/v1/auth/login", body=LOGIN)
if status != 200:
    raise SystemExit(f"login failed {status}: {text}")
token = json.loads(text)["accessToken"]

auth_config = {
    "clientType": "confidential",
    "provider": "custom-oidc",
    "responseType": "code",
    "providerName": "Keycloak",
    "publicKeyUrls": [
        "https://keycloak.datalabutehy.com/realms/data-team/protocol/openid-connect/certs"
    ],
    "tokenValidationAlgorithm": "RS256",
    "authority": "https://keycloak.datalabutehy.com/realms/data-team",
    "clientId": "openmetadata",
    "callbackUrl": "https://openmetadata.datalabutehy.com/callback",
    "jwtPrincipalClaims": ["email", "preferred_username", "sub"],
    "jwtPrincipalClaimsMapping": [],
    "enableSelfSignup": True,
    "forceSecureSessionCookie": True,
    "enableAutoRedirect": False,
}

authorizer_config = {
    "adminPrincipals": ["admin", "damquangthinh"],
    "testPrincipals": [],
    "allowedEmailRegistrationDomains": ["all"],
    "principalDomain": "open-metadata.org",
    "allowedDomains": [],
    "useRolesFromProvider": False,
}

candidate_paths = [
    "/api/v1/system/settings/authenticationConfiguration",
    "/api/v1/system/settings/authorizerConfiguration",
    "/api/v1/system/settings",
]

for path in candidate_paths:
    status, text = request("GET", path, token=token)
    print("GET", path, status, text[:500])

for name, config in [
    ("authenticationConfiguration", auth_config),
    ("authorizerConfiguration", authorizer_config),
]:
    for method in ["PUT", "PATCH", "POST"]:
        for path in [f"/api/v1/system/settings/{name}", f"/api/v1/system/settings"]:
            body = config if path.endswith(name) else {"config_type": name, "config_value": config}
            status, text = request(method, path, token=token, body=body)
            print(method, path, status, text[:500])
            if 200 <= status < 300:
                break
        else:
            continue
        break

status, text = request("GET", "/api/v1/system/config/auth", token=token)
print("FINAL_AUTH", status, text)
status, text = request("GET", "/api/v1/system/config/authorizer", token=token)
print("FINAL_AUTHORIZER", status, text)
