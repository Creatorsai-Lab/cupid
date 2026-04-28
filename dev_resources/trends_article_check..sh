$loginBody = @{
    email = "user@gmail.com"
    password = "12345678"
} | ConvertTo-Json

# Notice the new -SessionVariable parameter added at the end
$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $loginBody `
    -SessionVariable mySession

# Now, we look inside the session variable to find your cookie
$tokenCookie = $mySession.Cookies.GetCookies("http://localhost:8000") | Where-Object { $_.Name -eq "cupid_access_token" }

$token = $tokenCookie.Value

Write-Host "Got token: $($token.Substring(0,40))..."


# $headers = @{ Authorization = "Bearer $token" }

$trends = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/trends/news" `
    -Method GET `
    -Headers $headers

# See what came back
$trends

# To see the article titles only:
$trends.articles | Select-Object title, source, category