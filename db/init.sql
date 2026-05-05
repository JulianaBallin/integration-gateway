CREATE TABLE IF NOT EXISTS integration_audit (
    id BIGSERIAL PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    external_order_id TEXT,
    customer_code TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    external_payload JSONB NOT NULL,
    transformed_payload JSONB,
    internal_response JSONB,
    transformer_version TEXT NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_integration_audit_created_at ON integration_audit (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_integration_audit_status ON integration_audit (status);
CREATE INDEX IF NOT EXISTS idx_integration_audit_correlation_id ON integration_audit (correlation_id);
