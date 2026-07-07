# Deploy Airflow and Integrate Keycloak on Kubernetes

This short guide describes how to deploy Keycloak and Airflow, then enable Keycloak SSO for the Airflow web UI.

## 1. Environment

```text
Airflow URL:  https://airflow.k8s.tailnet:31662
Keycloak URL: https://keycloak.k8s.tailnet:31662
Realm:        data-team
Client ID:    airflow
Airflow:      2.11.0
Helm chart:   apache-airflow/airflow 1.21.0
```

Add the following entries to the hosts file on the client machine:

```text
100.119.252.2 airflow.k8s.tailnet
100.119.252.2 keycloak.k8s.tailnet
```

---

## 2. Deploy Keycloak

```bash
cd k8s-data-services/keycloak-operator

kubectl create namespace keycloak \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f .

kubectl get pods -n keycloak
```

Test access:

```bash
curl -vkI https://keycloak.k8s.tailnet:31662
```

---

## 3. Configure Keycloak

Open the Keycloak Admin Console.

### Create the realm

```text
Realm name: data-team
```

### Create the client

```text
Client ID: airflow
Client type: OpenID Connect
Client authentication: On
Standard flow: On
```

Configure the URLs:

```text
Root URL:
https://airflow.k8s.tailnet:31662

Valid redirect URIs:
https://airflow.k8s.tailnet:31662/oauth-authorized/keycloak

Valid post logout redirect URIs:
https://airflow.k8s.tailnet:31662/*

Web origins:
https://airflow.k8s.tailnet:31662
```

### Create client roles

Create the following roles under the `airflow` client:

```text
airflow_admin
airflow_op
airflow_user
airflow_viewer
airflow_public
```

Assign a role to each user:

```text
Users → Role mapping → Assign role → Filter by clients → airflow
```

### Add the Audience mapper

Go to:

```text
Clients → airflow → Client scopes → airflow-dedicated
→ Mappers → Configure a new mapper → Audience
```

Configure:

```text
Name: airflow-audience
Included Client Audience: airflow
Add to access token: On
Add to ID token: On
```

The access token must contain `airflow` in the `aud` claim:

```json
"aud": ["account", "airflow"]
```

---

## 4. Create Airflow Secrets

```bash
cd ../orchestration

kubectl create namespace orchestration \
  --dry-run=client -o yaml | kubectl apply -f -
```

Create the Keycloak client Secret:

```bash
read -s -p "Keycloak Client Secret: " KEYCLOAK_CLIENT_SECRET
echo

kubectl create secret generic airflow-keycloak \
  -n orchestration \
  --from-literal=KEYCLOAK_CLIENT_ID=airflow \
  --from-literal=KEYCLOAK_CLIENT_SECRET="$KEYCLOAK_CLIENT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

unset KEYCLOAK_CLIENT_SECRET
```

Create a persistent Airflow webserver Secret:

```bash
kubectl create secret generic airflow-webserver-secret \
  -n orchestration \
  --from-literal=webserver-secret-key="$(openssl rand -hex 32)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Do not regenerate this Secret on every deployment because it invalidates existing sessions.

---

## 5. Deploy Airflow

```bash
helm repo add apache-airflow https://airflow.apache.org
helm repo update

helm upgrade --install airflow apache-airflow/airflow \
  -n orchestration \
  --version 1.21.0 \
  -f ./values.yaml \
  --wait \
  --timeout 30m
```

Verify the deployment:

```bash
kubectl get pods -n orchestration
helm status airflow -n orchestration
```

---

## 6. Configure Airflow to Use Keycloak

In `values-keycloak-only.yaml`, configure the main values:

```yaml
webserverSecretKeySecretName: airflow-webserver-secret

config:
  webserver:
    base_url: "https://airflow.k8s.tailnet:31662"
    enable_proxy_fix: "True"
    proxy_fix_x_for: "1"
    proxy_fix_x_proto: "1"
    proxy_fix_x_host: "0"
    proxy_fix_x_port: "0"

webserver:
  env:
    - name: KEYCLOAK_CLIENT_ID
      valueFrom:
        secretKeyRef:
          name: airflow-keycloak
          key: KEYCLOAK_CLIENT_ID

    - name: KEYCLOAK_CLIENT_SECRET
      valueFrom:
        secretKeyRef:
          name: airflow-keycloak
          key: KEYCLOAK_CLIENT_SECRET

    - name: KEYCLOAK_PUBLIC_ISSUER
      value: "https://keycloak.k8s.tailnet:31662/realms/data-team"

    - name: KEYCLOAK_INTERNAL_REALM_URL
      value: "http://keycloak-service.keycloak.svc.cluster.local:8080/realms/data-team"
```

Use these OpenID Connect endpoints:

```text
Authorize:
https://keycloak.k8s.tailnet:31662/realms/data-team/protocol/openid-connect/auth

Token:
http://keycloak-service.keycloak.svc.cluster.local:8080/realms/data-team/protocol/openid-connect/token

UserInfo:
http://keycloak-service.keycloak.svc.cluster.local:8080/realms/data-team/protocol/openid-connect/userinfo

JWKS:
http://keycloak-service.keycloak.svc.cluster.local:8080/realms/data-team/protocol/openid-connect/certs
```

Configure role mapping in `webserver_config.py`:

```python
AUTH_ROLES_MAPPING = {
    "airflow_admin": ["Admin"],
    "airflow_op": ["Op"],
    "airflow_user": ["User"],
    "airflow_viewer": ["Viewer"],
    "airflow_public": ["Public"],
}
```

---

## 7. Apply the Keycloak Integration

```bash
helm upgrade airflow apache-airflow/airflow \
  -n orchestration \
  --version 1.21.0 \
  --reuse-values \
  -f ./values-keycloak-only.yaml \
  --wait \
  --timeout 30m
```

Verify the rollout:

```bash
helm history airflow -n orchestration
kubectl get pods -n orchestration

kubectl rollout status deployment/airflow-webserver \
  -n orchestration \
  --timeout=300s
```

---

## 8. Test Login

Open:

```text
https://airflow.k8s.tailnet:31662
```

Click **Sign In with keycloak**.

If login fails, check the webserver logs:

```bash
kubectl logs -n orchestration \
  deployment/airflow-webserver \
  --since=5m | grep -Ei 'oauth|keycloak|audience|jwks|error'
```

Common errors:

```text
Invalid redirect_uri
→ Check the Valid redirect URIs value and port 31662.

Missing jwks_uri
→ Add the Keycloak JWKS endpoint to the OAuth configuration.

Audience doesn't match
→ The Audience mapper must add airflow to the access token.

Invalid login
→ Check the user role and resource_access.airflow.roles claim.
```

## 9. Notes

Keycloak changes only the Airflow web UI login process. Scheduler, DAGs, Executor, PostgreSQL, and task execution remain unchanged.

Applications that call the Airflow REST API still need a separate API authentication method, such as Basic Auth or a service account.
