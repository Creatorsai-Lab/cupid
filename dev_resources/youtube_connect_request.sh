# create login body
$loginBody = @{
    email    = "user@gmail.com"
    password = "12345678"
} | ConvertTo-Json

# Create a session container that holds cookies
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# Log in — backend sets the auth cookie on $session
Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $loginBody `
    -WebSession $session

Write-Host "Logged in. Session ready." -ForegroundColor Green

$startResp = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/connections/youtube/connect" `
    -Method GET `
    -WebSession $session

Write-Host "`nGoogle authorization URL:" -ForegroundColor Cyan
Write-Host $startResp.authorization_url


# List your connections via the API
$conns = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/connections/" `
    -Method GET `
    -WebSession $session

# format the connect and see it
$conns | Format-List

# check the docker postgres DB row
docker exec -it cupid_postgres psql -U cupid -d cupid_db -c "SELECT id, platform, handle, sync_status, scopes, LEFT(access_token_encrypted, 50) AS token_preview FROM social_connections;"