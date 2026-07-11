$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:OPENMETADATA_BASE_URL) { $env:OPENMETADATA_BASE_URL } else { "https://openmetadata.datalabutehy.com" }
$Username = if ($env:OPENMETADATA_SSO_USERNAME) { $env:OPENMETADATA_SSO_USERNAME } else { "damquangthinh" }
$Password = $env:OPENMETADATA_SSO_PASSWORD

if (-not $Password) {
  throw "Set OPENMETADATA_SSO_PASSWORD before running this script."
}

function Get-SsoToken {
  $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
  $redirect = [System.Uri]::EscapeDataString("$BaseUrl/callback")
  $loginUrl = "$BaseUrl/api/v1/auth/login?redirectUri=$redirect"
  $loginPage = Invoke-WebRequest -Uri $loginUrl -WebSession $session -MaximumRedirection 10 -UseBasicParsing
  $formAction = [regex]::Match($loginPage.Content, '<form[^>]+action="([^"]+)"').Groups[1].Value
  if (-not $formAction) {
    throw "Keycloak login form not found"
  }

  $formAction = [System.Net.WebUtility]::HtmlDecode($formAction)
  $callback = Invoke-WebRequest `
    -Uri $formAction `
    -Method Post `
    -Body @{ username = $Username; password = $Password; login = "Sign In" } `
    -WebSession $session `
    -MaximumRedirection 10 `
    -UseBasicParsing

  $finalUrl = $callback.BaseResponse.ResponseUri.AbsoluteUri
  $idToken = [regex]::Match($finalUrl, '[?&]id_token=([^&]+)').Groups[1].Value
  if (-not $idToken) {
    throw "OpenMetadata SSO token not found in callback URL: $finalUrl"
  }

  [System.Uri]::UnescapeDataString($idToken)
}

function Invoke-OmApi {
  param(
    [string] $Method,
    [string] $Path,
    [object] $Body = $null
  )

  $headers = @{ Authorization = "Bearer $script:Token" }
  $args = @(
    "-k", "-s", "-w", "`n%{http_code}", "-X", $Method,
    "$BaseUrl$Path",
    "-H", "Authorization: Bearer $script:Token",
    "-H", "Content-Type: application/json"
  )

  if ($null -ne $Body) {
    $json = $Body | ConvertTo-Json -Depth 20 -Compress
    $bodyFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($bodyFile, $json)
    $args += @("--data-binary", "@$bodyFile")
  }

  $raw = & curl.exe @args
  if ($LASTEXITCODE -ne 0) {
    throw "curl failed for $Method $Path"
  }

  $status = ($raw | Select-Object -Last 1)
  $response = ($raw | Select-Object -First ($raw.Count - 1)) -join "`n"
  if ($status -lt "200" -or $status -ge "300") {
    throw "$Method $Path failed with HTTP ${status}: $response"
  }
  if ([string]::IsNullOrWhiteSpace($response)) {
    return $null
  }
  try {
    $response | ConvertFrom-Json
  } catch {
    throw "$Method $Path returned non-JSON response: $response"
  }
}

function Get-EntityByName {
  param(
    [string] $Kind,
    [string] $Name,
    [string] $Fields = ""
  )

  $encoded = [System.Uri]::EscapeDataString($Name)
  $path = "/api/v1/$Kind/name/$encoded"
  if ($Fields) {
    $path = "{0}?fields={1}" -f $path, $Fields
  }

  $raw = & curl.exe -k -s -w "`n%{http_code}" "$BaseUrl$path" -H "Authorization: Bearer $script:Token"
  $status = ($raw | Select-Object -Last 1)
  $body = ($raw | Select-Object -First ($raw.Count - 1)) -join "`n"
  if ($status -eq "404") {
    return $null
  }
  if ($status -lt "200" -or $status -ge "300") {
    throw "GET $path failed with HTTP ${status}: $body"
  }
  if ([string]::IsNullOrWhiteSpace($body)) {
    return $null
  }
  $body | ConvertFrom-Json
}

function Ensure-Policy {
  $policy = Get-EntityByName -Kind "policies" -Name "OpenMetadataAdminPolicy"
  if ($policy) {
    return $policy
  }

  Invoke-OmApi -Method "POST" -Path "/api/v1/policies" -Body @{
    name = "OpenMetadataAdminPolicy"
    displayName = "OpenMetadata Admin Policy"
    description = "Allows full administrative access for users in the OpenMetadata admin RBAC group."
    enabled = $true
    rules = @(
      @{
        name = "AllResourcesAllOperations"
        description = "Allow all metadata operations on all resources."
        effect = "allow"
        operations = @("All")
        resources = @("*")
      }
    )
  }
}

function Ensure-Role {
  $role = Get-EntityByName -Kind "roles" -Name "OpenMetadataAdminRole" -Fields "policies"
  if ($role) {
    return $role
  }

  Invoke-OmApi -Method "POST" -Path "/api/v1/roles" -Body @{
    name = "OpenMetadataAdminRole"
    displayName = "OpenMetadata Admin Role"
    description = "Admin role assigned to the Keycloak-backed OpenMetadata admin team."
    policies = @("OpenMetadataAdminPolicy")
  }
}

function Ensure-Team {
  param(
    [string] $Name,
    [string] $DisplayName,
    [string] $Description,
    [array] $DefaultRoleIds
  )

  $body = @{
    name = $Name
    displayName = $DisplayName
    description = $Description
    teamType = "Group"
    defaultRoles = $DefaultRoleIds
  }

  $existing = Get-EntityByName -Kind "teams" -Name $Name -Fields "defaultRoles,users"
  if ($existing) {
    Invoke-OmApi -Method "PUT" -Path "/api/v1/teams" -Body $body
  } else {
    Invoke-OmApi -Method "POST" -Path "/api/v1/teams" -Body $body
  }
}

$script:Token = Get-SsoToken

$dataConsumer = Get-EntityByName -Kind "roles" -Name "DataConsumer"
$dataSteward = Get-EntityByName -Kind "roles" -Name "DataSteward"
$adminPolicy = Ensure-Policy
$adminRole = Ensure-Role

Ensure-Team `
  -Name "openmetadata_admins" `
  -DisplayName "OpenMetadata Admins" `
  -Description "Keycloak-backed OpenMetadata administrators." `
  -DefaultRoleIds @($adminRole.id, $dataSteward.id)

Ensure-Team `
  -Name "openmetadata_stewards" `
  -DisplayName "OpenMetadata Stewards" `
  -Description "Keycloak-backed OpenMetadata data stewards." `
  -DefaultRoleIds @($dataSteward.id)

Ensure-Team `
  -Name "openmetadata_users" `
  -DisplayName "OpenMetadata Users" `
  -Description "Keycloak-backed OpenMetadata data consumers." `
  -DefaultRoleIds @($dataConsumer.id)

Invoke-OmApi -Method "GET" -Path "/api/v1/teams?limit=100&fields=defaultRoles,users"
