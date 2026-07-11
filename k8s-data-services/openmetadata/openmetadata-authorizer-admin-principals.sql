update openmetadata_settings
set json = jsonb_set(
  json,
  '{adminPrincipals}',
  '["admin", "admin@open-metadata.org", "damquangthinh", "thinhquangshin", "thinhquangshin@gmail.com"]'::jsonb
)
where configtype = 'authorizerConfiguration';

select json -> 'adminPrincipals' as admin_principals
from openmetadata_settings
where configtype = 'authorizerConfiguration';
