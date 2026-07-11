# OpenMetadata Keycloak SSO and RBAC

This document records the working setup for OpenMetadata SSO/RBAC through Keycloak.

## Current Endpoints

- OpenMetadata public URL: `https://openmetadata.datalabutehy.com`
- OpenMetadata local ingress host: `openmetadata.k8s.tailnet`
- Keycloak public URL: `https://keycloak.datalabutehy.com`
- Keycloak realm: `data-team`
- Keycloak client ID: `openmetadata`
- OpenMetadata namespace: `openmetadata`
- OpenMetadata service: `openmetadata.openmetadata.svc.cluster.local:8585`

## File Inventory

Keep these files:

- `openmetadata-values.yaml`
  - Main Helm values for OpenMetadata, PostgreSQL/OpenSearch connection, ingress hosts, and `/callback` route.
- `postgresql-values.yaml`
  - PostgreSQL values for OpenMetadata.
- `opensearch-values.yaml`
  - OpenSearch values for OpenMetadata.
- `openmetadata-ingress-public.yaml`
  - Applied ingress manifest with both local and public hosts.
  - Routes `/callback` to `openmetadata-callback-proxy`.
- `openmetadata-callback-proxy.yaml`
  - Small NGINX proxy that fixes OpenMetadata callback behavior:
    - `/callback?code=...` is forwarded to OpenMetadata backend.
    - `/callback?id_token=...` is redirected to `/auth/callback?...` for the SPA.
- `keycloak-openmetadata-client.json`
  - Keycloak client definition for `openmetadata`.
- `keycloak-openmetadata-groups-mapper.json`
  - Keycloak protocol mapper definition for the `groups` claim.
- `openmetadata-sso-settings.sql`
  - DB-backed OpenMetadata auth/authorizer settings.
  - This is required because OpenMetadata loads `authenticationConfiguration` from DB and can override env vars.
- `configure_openmetadata_rbac.ps1`
  - Idempotent-ish script to create OpenMetadata RBAC policy, role, and teams.
- `OPENMETADATA_KEYCLOAK_SSO_RBAC.md`
  - This document.

Removed as no longer needed:

- `configure_openmetadata_sso.py`
  - Failed/obsolete API-based attempt. OpenMetadata blocks auth settings through the system settings endpoint.
- `openmetadata-admin-login.json`
  - Temporary built-in admin login payload.
- `query-openmetadata-auth-settings.sql`
  - Temporary DB inspection query.
- `openmetadata-authorizer-admin-principals.sql`
  - Incremental SQL now covered by `openmetadata-sso-settings.sql`.
- `openmetadata-enable-groups-claim.sql`
  - Incremental SQL now covered by `openmetadata-sso-settings.sql`.
- `openmetadata-keycloak-secrets.yaml`
  - Early env-secret approach. The live config is DB-backed, so this file was misleading.

## Keycloak Setup

### 1. Login to Keycloak Admin CLI

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user damquangthinh \
  --password '<KEYCLOAK_ADMIN_PASSWORD>'
```

### 2. Create the OpenMetadata Client

The intended client config is stored in `keycloak-openmetadata-client.json`.

Important fields:

- `clientId`: `openmetadata`
- confidential client: enabled
- valid redirect URIs:
  - `https://openmetadata.datalabutehy.com/callback`
  - `https://openmetadata.datalabutehy.com/api/v1/callback`
- web origin:
  - `https://openmetadata.datalabutehy.com`

Create it if missing:

```bash
kubectl exec -i -n keycloak keycloak-0 -- sh -c \
  'cat > /tmp/keycloak-openmetadata-client.json' < /tmp/keycloak-openmetadata-client.json

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh create clients \
  -r data-team \
  -f /tmp/keycloak-openmetadata-client.json
```

Get the client ID and secret:

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh get clients \
  -r data-team \
  -q clientId=openmetadata

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh get clients/<CLIENT_UUID>/client-secret \
  -r data-team
```

Update the secret in `openmetadata-sso-settings.sql` if the client secret changes.

### 3. Create RBAC Groups

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh create groups -r data-team -s name=openmetadata_admins

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh create groups -r data-team -s name=openmetadata_stewards

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh create groups -r data-team -s name=openmetadata_users
```

Group meaning:

- `openmetadata_admins`: OpenMetadata admins.
- `openmetadata_stewards`: users who can update metadata broadly.
- `openmetadata_users`: normal consumers/readers.

### 4. Add Users to Groups

Find the user and group IDs:

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh get users \
  -r data-team \
  -q username=damquangthinh \
  --fields id,username,email,enabled,requiredActions

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh get groups \
  -r data-team \
  --fields id,name
```

Assign a user to a group:

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh update users/<USER_UUID>/groups/<GROUP_UUID> \
  -r data-team \
  -n
```

For the current admin user, the expected groups are:

- `openmetadata_admins`
- `openmetadata_stewards`
- `openmetadata_users`

### 5. Add Groups Claim Mapper

The mapper is stored in `keycloak-openmetadata-groups-mapper.json`.

Because the Keycloak image does not have `tar`, avoid `kubectl cp`; stream the file into the pod:

```bash
kubectl exec -i -n keycloak keycloak-0 -- sh -c \
  'cat > /tmp/keycloak-openmetadata-groups-mapper.json' < /tmp/keycloak-openmetadata-groups-mapper.json

kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh create clients/<CLIENT_UUID>/protocol-mappers/models \
  -r data-team \
  -f /tmp/keycloak-openmetadata-groups-mapper.json
```

Verify:

```bash
kubectl exec -n keycloak keycloak-0 -- \
  /opt/keycloak/bin/kcadm.sh get clients/<CLIENT_UUID>/protocol-mappers/models \
  -r data-team \
  --fields id,name,protocolMapper,config
```

Expected mapper:

- name: `openmetadata-groups`
- protocol mapper: `oidc-group-membership-mapper`
- claim name: `groups`
- ID token claim: `true`
- access token claim: `true`
- full path: `false`

## OpenMetadata Setup

### 1. Deploy Callback Proxy

Apply:

```bash
kubectl apply -f openmetadata-callback-proxy.yaml
kubectl rollout status deployment/openmetadata-callback-proxy -n openmetadata --timeout=180s
```

Why this exists:

OpenMetadata 1.13.1 uses backend `/callback` for the OIDC code exchange and then redirects the browser with `id_token`.
The frontend route for that token should be `/auth/callback`, not backend `/callback`.

The proxy keeps both behaviors working:

- `/callback?code=...` -> OpenMetadata backend
- `/callback?id_token=...` -> `https://openmetadata.datalabutehy.com/auth/callback?...`

### 2. Apply Ingress

Apply:

```bash
kubectl apply -f openmetadata-ingress-public.yaml
kubectl describe ingress openmetadata -n openmetadata
```

Expected paths:

- `openmetadata.k8s.tailnet/callback` -> `openmetadata-callback-proxy:80`
- `openmetadata.k8s.tailnet/` -> `openmetadata:8585`
- `openmetadata.datalabutehy.com/callback` -> `openmetadata-callback-proxy:80`
- `openmetadata.datalabutehy.com/` -> `openmetadata:8585`

### 3. Apply DB-Backed SSO Settings

Copy SQL to the master node, then into the PostgreSQL pod:

```bash
scp openmetadata-sso-settings.sql hduser@master:/tmp/openmetadata-sso-settings.sql

ssh hduser@master \
  "kubectl cp /tmp/openmetadata-sso-settings.sql openmetadata/openmetadata-postgresql-0:/tmp/openmetadata-sso-settings.sql"
```

Run it:

```bash
ssh hduser@master \
  "kubectl exec -n openmetadata openmetadata-postgresql-0 -- \
   env PGPASSWORD='OpenMetadata@123' \
   psql -U openmetadata_user -d openmetadata_db \
   -f /tmp/openmetadata-sso-settings.sql"
```

Important values in `openmetadata-sso-settings.sql`:

- `provider`: `custom-oidc`
- `authority`: `https://keycloak.datalabutehy.com/realms/data-team`
- `clientId`: `openmetadata`
- `callbackUrl`: `https://openmetadata.datalabutehy.com/callback`
- `oidcConfiguration.discoveryUri`: `https://keycloak.datalabutehy.com/realms/data-team/.well-known/openid-configuration`
- `jwtPrincipalClaims`: `email`, `preferred_username`, `sub`
- `jwtTeamClaimMapping`: `groups`
- `adminPrincipals`: includes `admin`, `damquangthinh`, `thinhquangshin`, and `thinhquangshin@gmail.com`

Restart OpenMetadata:

```bash
kubectl rollout restart deployment/openmetadata -n openmetadata
kubectl rollout status deployment/openmetadata -n openmetadata --timeout=420s
```

### 4. Configure OpenMetadata RBAC Objects

Run the script from a Windows PowerShell terminal in the repo root.

Set the SSO password in the environment first:

```powershell
$env:OPENMETADATA_SSO_USERNAME = "damquangthinh"
$env:OPENMETADATA_SSO_PASSWORD = "<KEYCLOAK_DATA_TEAM_PASSWORD>"
$env:OPENMETADATA_BASE_URL = "https://openmetadata.datalabutehy.com"

powershell -ExecutionPolicy Bypass -File k8s-data-services/openmetadata/configure_openmetadata_rbac.ps1
```

The script creates or updates:

- Policy: `OpenMetadataAdminPolicy`
  - Rule: `AllResourcesAllOperations`
  - Operations: `All`
  - Resources: `*`
- Role: `OpenMetadataAdminRole`
  - Policy: `OpenMetadataAdminPolicy`
- Team: `openmetadata_admins`
  - Default roles: `OpenMetadataAdminRole`, `DataSteward`
- Team: `openmetadata_stewards`
  - Default role: `DataSteward`
- Team: `openmetadata_users`
  - Default role: `DataConsumer`

## Verification

### 1. Verify Public Auth Config

```bash
curl -k -s https://openmetadata.datalabutehy.com/api/v1/system/config/auth
```

Expected:

- `provider`: `custom-oidc`
- `clientType`: `confidential`
- `authority`: `https://keycloak.datalabutehy.com/realms/data-team`
- `clientId`: `openmetadata`
- `callbackUrl`: `https://openmetadata.datalabutehy.com/callback`

### 2. Verify Redirect URL

```bash
curl -k -s -D - -o /dev/null \
  "https://openmetadata.datalabutehy.com/api/v1/auth/login?redirectUri=https%3A%2F%2Fopenmetadata.datalabutehy.com%2Fcallback"
```

Expected `Location`:

```text
https://keycloak.datalabutehy.com/realms/data-team/protocol/openid-connect/auth?...redirect_uri=https%3A%2F%2Fopenmetadata.datalabutehy.com%2Fcallback...
```

### 3. Verify Login Result

After successful browser login, the browser should land on:

```text
https://openmetadata.datalabutehy.com/auth/callback?id_token=...
```

The app should then load normally.

### 4. Verify Groups Claim and RBAC

After login, the ID token should contain:

```json
"groups": [
  "openmetadata_admins",
  "openmetadata_stewards",
  "openmetadata_users"
]
```

The OpenMetadata user `thinhquangshin` should have:

- teams:
  - `openmetadata_admins`
  - `openmetadata_stewards`
  - `openmetadata_users`
- inherited roles:
  - `OpenMetadataAdminRole`
  - `DataSteward`
  - `DataConsumer`

## Operational Notes

- OpenMetadata 1.13.1 adds teams from the OIDC `groups` claim during login.
- It does not automatically remove teams if a user is later removed from a Keycloak group. For privilege reduction, remove the team membership in OpenMetadata or add a reconciliation job.
- Auth settings are DB-backed. If the API still returns `provider: basic`, check `openmetadata_settings` in PostgreSQL.
- The Keycloak client secret appears in DB-backed SSO config. Rotate it if this repository is shared beyond the cluster admin boundary.
- If Keycloak login shows required actions such as `UPDATE_PASSWORD` or `VERIFY_PROFILE`, clear them or complete the profile for the user in the `data-team` realm.
