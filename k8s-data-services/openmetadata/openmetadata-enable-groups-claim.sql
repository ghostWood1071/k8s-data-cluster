update openmetadata_settings
set json = jsonb_set(json, '{jwtTeamClaimMapping}', '"groups"'::jsonb, true)
where configtype = 'authenticationConfiguration';

select json ->> 'jwtTeamClaimMapping' as jwt_team_claim_mapping
from openmetadata_settings
where configtype = 'authenticationConfiguration';
