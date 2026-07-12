import html
import re
import ssl
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


USERNAME = sys.argv[1]
PASSWORD = sys.argv[2]
START_URL = "https://airflow.datalabutehy.com/login/keycloak?next=https%3A%2F%2Fairflow.datalabutehy.com%2Fhome"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


ctx = ssl._create_unverified_context()
cookies = CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookies),
    urllib.request.HTTPSHandler(context=ctx),
)
no_redirect = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookies),
    urllib.request.HTTPSHandler(context=ctx),
    NoRedirect,
)


def request(url, data=None, follow=True):
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "codex-airflow-keycloak-test/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST" if data is not None else "GET",
    )
    client = opener if follow else no_redirect
    try:
        return client.open(req, timeout=30)
    except urllib.error.HTTPError as exc:
        return exc


resp = request(START_URL, follow=True)
html_body = resp.read().decode("utf-8", errors="replace")
current_url = resp.geturl()

match = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', html_body)
if not match:
    print("FAILED: Keycloak login form not found")
    print("URL:", current_url)
    print(html_body[:500])
    sys.exit(1)

action = html.unescape(match.group(1))
payload = urllib.parse.urlencode(
    {
        "username": USERNAME,
        "password": PASSWORD,
        "credentialId": "",
    }
).encode()

resp = request(action, payload, follow=False)
status = getattr(resp, "code", None)
location = resp.headers.get("Location")
print("POST_LOGIN_STATUS:", status)
print("POST_LOGIN_LOCATION:", location)

if not location:
    body = resp.read().decode("utf-8", errors="replace")
    if "Invalid username or password" in body:
        print("FAILED: Keycloak rejected username/password")
    else:
        print("FAILED: No redirect after Keycloak login")
    print(body[:800])
    sys.exit(1)

callback = urllib.parse.urljoin(action, location)
resp = request(callback, follow=True)
final_url = resp.geturl()
final_status = getattr(resp, "code", None)
final_body = resp.read().decode("utf-8", errors="replace")

print("FINAL_STATUS:", final_status)
print("FINAL_URL:", final_url)
if "Invalid login. Please try again." in final_body:
    print("FAILED: Airflow rejected OAuth callback")
    sys.exit(1)
if "/logout/" in final_body or "Browse" in final_body or "DAGs" in final_body:
    print("SUCCESS: Airflow session established")
    sys.exit(0)

print("UNKNOWN: Callback completed but Airflow home markers were not found")
print(final_body[:800])
sys.exit(2)
