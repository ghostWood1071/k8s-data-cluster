begin;

update openmetadata_settings
set json = '
{
  "enabled": true,
  "clientType": "confidential",
  "provider": "custom-oidc",
  "publicKeys": [
    "https://openmetadata.datalabutehy.com/api/v1/system/config/jwks",
    "https://keycloak.datalabutehy.com/realms/data-team/protocol/openid-connect/certs"
  ],
  "authority": "https://keycloak.datalabutehy.com/realms/data-team/protocol/openid-connect/auth",
  "clientId": "openmetadata",
  "callbackUrl": "https://openmetadata.datalabutehy.com/callback",
  "enableSelfSignup": true,
  "jwtPrincipalClaims": ["email", "preferred_username", "sub"],
  "jwtTeamClaimMapping": "groups",
  "oidcConfiguration": {
    "enabled": true,
    "oidcType": "Keycloak",
    "clientId": "openmetadata",
    "secret": "__OPENMETADATA_OIDC_CLIENT_SECRET__",
    "scope": "openid email profile",
    "discoveryUri": "https://keycloak.datalabutehy.com/realms/data-team/.well-known/openid-configuration",
    "useNonce": true,
    "preferredJwsAlgorithm": "RS256",
    "responseType": "code",
    "disablePkce": true,
    "callbackUrl": "https://openmetadata.datalabutehy.com/callback",
    "serverUrl": "https://openmetadata.datalabutehy.com",
    "clientAuthenticationMethod": "client_secret_post",
    "tenant": "data-team"
  }
}'::jsonb
where configtype = 'authenticationConfiguration';

update openmetadata_settings
set json = jsonb_set(
  jsonb_set(
    jsonb_set(
      jsonb_set(json, '{className}', '"org.openmetadata.service.security.DefaultAuthorizer"'::jsonb, true),
      '{containerRequestFilter}', '"org.openmetadata.service.security.JwtFilter"'::jsonb, true
    ),
    '{initialAdmins}', '["temp-admin", "admin", "damquangthinh"]'::jsonb, true
  ),
  '{principalDomain}', '"datalabutehy.com"'::jsonb, true
)
where configtype = 'authorizerConfiguration';

commit;

select configtype, json ->> 'provider' as provider, json ->> 'clientId' as client_id, json ->> 'jwtTeamClaimMapping' as team_claim
from openmetadata_settings
where configtype = 'authenticationConfiguration';
