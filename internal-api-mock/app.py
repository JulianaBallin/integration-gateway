from flask import Flask, request, jsonify
import os
import socket
import time

PORT = int(os.getenv("INTERNAL_API_PORT", "8200"))
app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({
        "service": "internal-api-mock",
        "status": "healthy",
        "hostname": socket.gethostname()
    })

@app.post("/legacy/orders")
def legacy_orders():
    payload = request.get_json(force=True, silent=True)

    if payload is None:
        return jsonify({"status": "rejected", "error": "invalid JSON"}), 400

    required = ["legacy_order_id", "legacy_customer_code", "legacy_total_items", "legacy_items"]

    missing = [field for field in required if field not in payload]
    if missing:
        print(f"[internal-api-mock] rejected missing={missing} payload={payload}", flush=True)
        return jsonify({
            "status": "rejected",
            "error": "contract violation",
            "missing_fields": missing
        }), 422

    if not isinstance(payload["legacy_items"], list) or len(payload["legacy_items"]) == 0:
        return jsonify({
            "status": "rejected",
            "error": "legacy_items must be a non-empty list"
        }), 422

    print(f"[internal-api-mock] accepted legacy_order_id={payload['legacy_order_id']}", flush=True)

    return jsonify({
        "status": "accepted",
        "legacy_protocol": "LEGACY_ORDER_V1",
        "legacy_order_id": payload["legacy_order_id"],
        "processed_at": time.time(),
        "internal_hostname": socket.gethostname()
    }), 201

if __name__ == "__main__":
    print(f"[internal-api-mock] starting on port {PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
