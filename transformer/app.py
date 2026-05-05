from flask import Flask, request, jsonify
import json
import os
import socket
import time
import requests
import psycopg2

PORT = int(os.getenv("TRANSFORMER_PORT", "8100"))
INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://internal-api-mock:8200/legacy/orders")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "integrationdb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "integration_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "integration_pass")

TRANSFORMER_VERSION = "stable-v1"

app = Flask(__name__)

def db():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )

def save_audit(correlation_id, external_payload, transformed_payload, internal_response, status, error_message=None):
    external_order_id = external_payload.get("order_id")
    customer_code = external_payload.get("customer", {}).get("code")

    with db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO integration_audit (
                    correlation_id,
                    external_order_id,
                    customer_code,
                    status,
                    error_message,
                    external_payload,
                    transformed_payload,
                    internal_response,
                    transformer_version
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                ''',
                (
                    correlation_id,
                    external_order_id,
                    customer_code,
                    status,
                    error_message,
                    json.dumps(external_payload),
                    json.dumps(transformed_payload) if transformed_payload is not None else None,
                    json.dumps(internal_response) if internal_response is not None else None,
                    TRANSFORMER_VERSION,
                ),
            )

def validate_external(payload):
    required = ["order_id", "customer", "items"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"missing required external fields: {missing}")

    if "code" not in payload["customer"]:
        raise ValueError("missing customer.code")

    if not isinstance(payload["items"], list) or len(payload["items"]) == 0:
        raise ValueError("items must be a non-empty list")

def transform_payload(payload):
    total_quantity = sum(int(item.get("quantity", 0)) for item in payload["items"])

    legacy_items = []
    for item in payload["items"]:
        legacy_items.append({
            "legacy_sku": str(item["sku"]),
            "legacy_qty": int(item["quantity"])
        })

    return {
        "legacy_order_id": str(payload["order_id"]),
        "legacy_customer_code": str(payload["customer"]["code"]),
        "legacy_total_items": total_quantity,
        "legacy_items": legacy_items,
        "source_contract": "EXTERNAL_ORDER_V2",
        "transformed_at": time.time(),
        "transformer_hostname": socket.gethostname()
    }

@app.get("/health")
def health():
    try:
        with db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        return jsonify({
            "service": "transformer",
            "status": "healthy",
            "hostname": socket.gethostname(),
            "version": TRANSFORMER_VERSION
        })
    except Exception as exc:
        return jsonify({
            "service": "transformer",
            "status": "unhealthy",
            "error": str(exc)
        }), 500

@app.post("/transform")
def transform():
    envelope = request.get_json(force=True)
    correlation_id = envelope.get("correlation_id")
    external_payload = envelope.get("payload", {})

    try:
        validate_external(external_payload)
        transformed = transform_payload(external_payload)

        response = requests.post(INTERNAL_API_URL, json=transformed, timeout=10)
        internal_body = response.json()

        if response.status_code >= 400:
            save_audit(
                correlation_id,
                external_payload,
                transformed,
                internal_body,
                "FAILED",
                f"internal API rejected payload with status {response.status_code}"
            )
            print(f"[transformer] FAILED correlation_id={correlation_id} internal_status={response.status_code}", flush=True)
            return jsonify({
                "status": "failed",
                "correlation_id": correlation_id,
                "internal_status": response.status_code,
                "internal_response": internal_body,
                "transformer_version": TRANSFORMER_VERSION
            }), 502

        save_audit(correlation_id, external_payload, transformed, internal_body, "SUCCESS")

        print(f"[transformer] SUCCESS correlation_id={correlation_id} order_id={external_payload.get('order_id')}", flush=True)

        return jsonify({
            "status": "success",
            "correlation_id": correlation_id,
            "internal_response": internal_body,
            "transformer_version": TRANSFORMER_VERSION
        }), 201

    except Exception as exc:
        save_audit(correlation_id, external_payload, None, None, "FAILED", str(exc))
        print(f"[transformer] ERROR correlation_id={correlation_id} error={exc}", flush=True)
        return jsonify({
            "status": "failed",
            "correlation_id": correlation_id,
            "error": str(exc),
            "transformer_version": TRANSFORMER_VERSION
        }), 400

if __name__ == "__main__":
    print(f"[transformer] starting on port {PORT} version={TRANSFORMER_VERSION}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
