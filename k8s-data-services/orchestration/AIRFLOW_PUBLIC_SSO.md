# Airflow public SSO checklist

Airflow is exposed internally through `http://airflow.k8s.tailnet:30296`, but the browser-facing URL must be treated as:

```text
https://airflow.datalabutehy.com
```

Required settings:

- Airflow `[webserver] base_url`: `https://airflow.datalabutehy.com`
- Airflow proxy fix: `enable_proxy_fix=True`, `proxy_fix_x_proto=1`, `proxy_fix_x_host=1`, `proxy_fix_x_port=0`
- Keycloak issuer: `https://keycloak.datalabutehy.com/realms/data-team`
- Keycloak client: `airflow`
- Keycloak valid redirect URI: `https://airflow.datalabutehy.com/oauth-authorized/keycloak`
- Keycloak web origin: `https://airflow.datalabutehy.com`
- Airflow users must exist in the `data-team` realm, not only in the `master` realm.
- Airflow users need one client role on client `airflow`: `airflow_admin`, `airflow_op`, `airflow_user`, `airflow_viewer`, or `airflow_public`.

Cloudflare tunnel route for `/etc/cloudflared/config-dataplatform.yml`:

```yaml
ingress:
  - hostname: airflow.datalabutehy.com
    service: http://airflow.k8s.tailnet:30296
  - service: http_status:404
```

Do not set `originRequest.httpHostHeader: airflow.k8s.tailnet` for this route unless you also preserve `X-Forwarded-Host: airflow.datalabutehy.com`. The Kubernetes ingress now accepts both `airflow.k8s.tailnet` and `airflow.datalabutehy.com`.

The NGINX ingress controller must preserve forwarded headers from Cloudflare:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ingress-nginx-controller
  namespace: load-balancer
data:
  use-forwarded-headers: "true"
  compute-full-forwarded-for: "true"
  enable-real-ip: "true"
```

After applying the Helm overlay, verify that the login URL no longer contains the internal host:

```bash
curl -kI https://airflow.datalabutehy.com/login/
```

If the browser shows a native username/password popup, the request has not reached Airflow yet. Check these first:

```bash
kubectl get ingress -A | grep -E 'airflow|longhorn|volume'
kubectl describe ingress airflow-webserver -n orchestration | grep -i 'auth'
kubectl annotate ingress airflow-webserver -n orchestration \
  nginx.ingress.kubernetes.io/auth-type- \
  nginx.ingress.kubernetes.io/auth-secret- \
  nginx.ingress.kubernetes.io/auth-realm- \
  nginx.ingress.kubernetes.io/auth-url- \
  nginx.ingress.kubernetes.io/auth-signin- \
  --overwrite
sudo grep -n -A8 -B2 'airflow.datalabutehy.com' /etc/cloudflared/config-dataplatform.yml
```

The expected public header after fixing the ingress/tunnel must not contain `WWW-Authenticate: Basic`:

```bash
curl -kI https://airflow.datalabutehy.com
```
