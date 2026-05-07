# Get logged in (same session pattern as before):

$loginBody = @{
    email    = "your_email"
    password = "your_password"
} | ConvertTo-Json

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $loginBody `
    -WebSession $session

# Test the list endpoint
$summaries = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/insights/" `
    -Method GET `
    -WebSession $session
$summaries | Format-List

# Test the four dashboard endpoints
$cid = $summaries[0].connection_id

# Summary
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/insights/$cid/summary" -WebSession $session | Format-List

# Time series (last 30 days)
$ts = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/insights/$cid/timeseries?range_days=30" -WebSession $session
Write-Host "Got $($ts.points.Count) timeseries points"
$ts.points | Format-Table

# Top content
$top = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/insights/$cid/top-content?limit=5" -WebSession $session
Write-Host "Top 5:"
$top.items | Select-Object rank, title, views, likes | Format-Table

# Heatmap
$hm = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/insights/$cid/heatmap" -WebSession $session
Write-Host "Heatmap insight: $($hm.insight)"
Write-Host "Cells with data: $($hm.cells.Count)"

# Test the auth gate (security check)
try {
    Invoke-RestMethod `
        -Uri "http://localhost:8000/api/v1/insights/00000000-0000-0000-0000-000000000000/summary" `
        -WebSession $session
} catch {
    Write-Host "Got expected error: $($_.Exception.Response.StatusCode)"
}
