update openmetadata_settings
set json = $${
  "clientId": "openmetadata",
  "provider": "custom-oidc",
  "authority": "https://keycloak.datalabutehy.com/realms/data-team",
  "clientType": "confidential",
  "callbackUrl": "https://openmetadata.datalabutehy.com/callback",
  "providerName": "Keycloak",
  "responseType": "code",
  "publicKeyUrls": [
    "https://keycloak.datalabutehy.com/realms/data-team/protocol/openid-connect/certs"
  ],
  "enableSelfSignup": true,
  "ldapConfiguration": {
    "isFullDn": false,
    "sslEnabled": false,
    "userBaseDN": "",
    "groupBaseDN": "",
    "maxPoolSize": 3,
    "dnAdminPassword": "",
    "authRolesMapping": "",
    "dnAdminPrincipal": "",
    "trustStoreConfig": {
      "hostNameConfig": {
        "allowWildCards": false,
        "acceptableHostNames": []
      },
      "trustAllConfig": {
        "examineValidityDates": true
      },
      "jvmDefaultConfig": {
        "verifyHostname": false
      },
      "customTrustManagerConfig": {
        "verifyHostname": false,
        "examineValidityDates": false
      }
    },
    "authReassignRoles": [],
    "truststoreConfigType": "TrustAll"
  },
  "oidcConfiguration": {
    "id": "openmetadata",
    "type": "customOidc",
    "scope": "openid email profile",
    "maxAge": "0",
    "prompt": "consent",
    "secret": "s3cXPbigflkwFSot9ckf4kBERTHwRWhn",
    "tenant": "",
    "useNonce": "true",
    "serverUrl": "https://keycloak.datalabutehy.com",
    "callbackUrl": "https://openmetadata.datalabutehy.com/callback",
    "disablePkce": true,
    "discoveryUri": "https://keycloak.datalabutehy.com/realms/data-team/.well-known/openid-configuration",
    "maxClockSkew": "",
    "responseType": "code",
    "sessionExpiry": 604800,
    "tokenValidity": 3600,
    "preferredJwsAlgorithm": "RS256",
    "clientAuthenticationMethod": "client_secret_post"
  },
  "samlConfiguration": {
    "sp": {
      "acs": "http://localhost:8585/api/v1/saml/acs",
      "callback": "http://localhost:8585/saml/callback",
      "entityId": "http://localhost:8585/api/v1/saml/metadata",
      "spPrivateKey": "",
      "spX509Certificate": ""
    },
    "idp": {
      "nameId": "urn:oasis:names:tc:SAML:2.0:nameid-format:emailAddress",
      "entityId": "",
      "ssoLoginUrl": "",
      "idpX509Certificate": ""
    },
    "security": {
      "strictMode": false,
      "validateXml": false,
      "keyStoreAlias": "",
      "tokenValidity": 3600,
      "signSpMetadata": false,
      "keyStoreFilePath": "",
      "keyStorePassword": "",
      "wantMessagesSigned": false,
      "sendEncryptedNameId": false,
      "wantAssertionsSigned": false,
      "sendSignedAuthRequest": false,
      "wantAssertionEncrypted": false
    },
    "debugMode": false,
    "samlDisplayNameAttributes": []
  },
  "enableAutoRedirect": false,
  "jwtPrincipalClaims": [
    "email",
    "preferred_username",
    "sub"
  ],
  "forceSecureSessionCookie": true,
  "tokenValidationAlgorithm": "RS256",
  "jwtPrincipalClaimsMapping": []
}$$::jsonb
where configtype = 'authenticationConfiguration';

update openmetadata_settings
set json = $${
  "className": "org.openmetadata.service.security.DefaultAuthorizer",
  "allowedDomains": [],
  "testPrincipals": [],
  "adminPrincipals": [
    "admin",
    "admin@open-metadata.org",
    "damquangthinh",
    "thinhquangshin",
    "thinhquangshin@gmail.com"
  ],
  "principalDomain": "open-metadata.org",
  "useRolesFromProvider": false,
  "containerRequestFilter": "org.openmetadata.service.security.JwtFilter",
  "enforcePrincipalDomain": false,
  "enableSecureSocketConnection": false,
  "allowedEmailRegistrationDomains": [
    "all"
  ]
}$$::jsonb
where configtype = 'authorizerConfiguration';

select configtype, json
from openmetadata_settings
where configtype in ('authenticationConfiguration', 'authorizerConfiguration');
