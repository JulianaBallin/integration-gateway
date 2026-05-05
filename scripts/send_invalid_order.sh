#!/usr/bin/env sh
curl -X POST http://localhost:8000/integrations \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: demo-invalid-001" \
  --data-binary @payloads/invalid-order.json
echo
