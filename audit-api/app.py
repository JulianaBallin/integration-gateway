from flask import Flask, jsonify, request
import os
import socket
import psycopg2
import psycopg2.extras

PORT = int(os.getenv("AUDIT_API_PORT", "8300"))

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "integrationdb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "integration_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "integration_pass")

app = Flask(__name__)

def db():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

@app.get("/")
def index():
    return jsonify({
        "name": "Integration Gateway Audit API",
        "routes": ["/health", "/audits", "/audits/summary", "/audits/<correlation_id>"]
    })

@app.get("/health")
def health():
    with db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
    return jsonify({
        "service": "audit-api",
        "status": "healthy",
        "hostname": socket.gethostname()
    })

@app.get("/audits")
def audits():
    limit = min(int(request.args.get("limit", "20")), 100)
    with db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT id, correlation_id, external_order_id, customer_code, status,
                       error_message, transformer_version, created_at
                FROM integration_audit
                ORDER BY created_at DESC
                LIMIT %s
                ''',
                (limit,),
            )
            return jsonify(cursor.fetchall())

@app.get("/audits/summary")
def summary():
    with db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT status, transformer_version, COUNT(*) AS total
                FROM integration_audit
                GROUP BY status, transformer_version
                ORDER BY total DESC
                '''
            )
            return jsonify(cursor.fetchall())

@app.get("/audits/<correlation_id>")
def audit_detail(correlation_id):
    with db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT *
                FROM integration_audit
                WHERE correlation_id = %s
                ORDER BY created_at DESC
                ''',
                (correlation_id,),
            )
            return jsonify(cursor.fetchall())

if __name__ == "__main__":
    print(f"[audit-api] starting on port {PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
