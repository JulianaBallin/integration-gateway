$body = Get-Content -Raw -Path "payloads\invalid-order.json"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/integrations" `
  -Headers @{ "X-Correlation-ID" = "demo-invalid-001" } `
  -ContentType "application/json" `
  -Body $body
