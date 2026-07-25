# OpenMetadata Keycloak SSO and RBAC

Runtime endpoints:

- OpenMetadata: `https://openmetadata.datalabutehy.com`
- Keycloak: `https://keycloak.datalabutehy.com`
- Realm: `data-team`
- Client ID: `openmetadata`

Keep the deploy surface small:

- `openmetadata-values.yaml`: Helm values for OpenMetadata OIDC/RBAC, database, search, pipeline client, and ingress.
- `openmetadata-callback-proxy.yaml`: callback compatibility proxy for OpenMetadata SSO.
- `openmetadata-ingress-public.yaml`: public/tailnet ingress for OpenMetadata and `/callback`.
- `openmetadata-sso-settings.sql`: DB-backed auth settings when OpenMetadata overrides Helm/env auth config.
- `configure_openmetadata_rbac.ps1`: creates/repairs OpenMetadata RBAC teams, roles, and policies.
- `keycloak-openmetadata-client.json`: Keycloak client shape for reference/import.
- `keycloak-openmetadata-groups-mapper.json`: Keycloak groups claim mapper for reference/import.

Important RBAC note: OpenMetadata policy rules must use `resources: ["All"]` for all resources. Do not use `*`; it results in `conditionalAllow` and users cannot add services reliably.

Important OIDC note: PKCE is disabled because the current OpenMetadata callback flow does not send `code_challenge_method`.

Secret handling: The Kubernetes Secret `oidc-secrets` is required by `openmetadata-values.yaml`, but it must be created outside source control. Do not commit the client secret into this folder.

Before running openmetadata-sso-settings.sql, replace __OPENMETADATA_OIDC_CLIENT_SECRET__ with the live Keycloak client secret in a temporary local copy or pass it through your secure secret workflow.
