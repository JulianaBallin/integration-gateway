from flask import Flask, request, jsonify
import os
import socket
import uuid
import requests

TRANSFORMER_URL = os.getenv("TRANSFORMER_URL", "http://transformer:8100/transform")
PORT = int(os.getenv("GATEWAY_PORT", "8000"))

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({
        "service": "gateway-api",
        "status": "healthy",
        "hostname": socket.gethostname(),
        "transformer_url": TRANSFORMER_URL
    })

@app.post("/integrations")
def integrations():
    payload = request.get_json(force=True, silent=True)

    if payload is None:
        return jsonify({"status": "rejected", "error": "invalid JSON"}), 400

    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    try:
        response = requests.post(
            TRANSFORMER_URL,
            json={
                "correlation_id": correlation_id,
                "payload": payload,
                "received_by": socket.gethostname()
            },
            timeout=10
        )

        print(f"[gateway-api] correlation_id={correlation_id} transformer_status={response.status_code}", flush=True)

        return jsonify({
            "gateway": "accepted",
            "correlation_id": correlation_id,
            "transformer_status": response.status_code,
            "transformer_response": response.json()
        }), response.status_code

    except Exception as exc:
        print(f"[gateway-api] correlation_id={correlation_id} error={exc}", flush=True)
        return jsonify({
            "status": "failed",
            "correlation_id": correlation_id,
            "error": str(exc)
        }), 502

if __name__ == "__main__":
    print(f"[gateway-api] starting on port {PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
