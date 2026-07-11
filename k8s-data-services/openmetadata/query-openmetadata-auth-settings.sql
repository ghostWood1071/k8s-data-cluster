select configtype, json
from openmetadata_settings
where configtype in ('authenticationConfiguration', 'authorizerConfiguration');
