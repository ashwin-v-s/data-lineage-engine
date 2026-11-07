-- Idempotency and delivery status for welcome emails sent after login.
CREATE TABLE kairos_welcome_email_delivery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    event_id UUID NOT NULL,
    recipient_email TEXT NOT NULL CHECK (length(btrim(recipient_email)) BETWEEN 3 AND 320),
    delivery_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (delivery_status IN ('PENDING', 'SENT', 'FAILED')),
    failure_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    CONSTRAINT kairos_welcome_email_delivery_event_key UNIQUE (workspace_id, user_id, event_id)
);

CREATE INDEX idx_kairos_welcome_email_user
    ON kairos_welcome_email_delivery (workspace_id, user_id, created_at DESC);

ALTER TABLE kairos_welcome_email_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE kairos_welcome_email_delivery FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON kairos_welcome_email_delivery
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

REVOKE ALL ON TABLE kairos_welcome_email_delivery FROM PUBLIC;
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'kairos_welcome_email_delivery', r);
        END IF;
    END LOOP;
END $$;
GRANT SELECT, INSERT, UPDATE ON TABLE kairos_welcome_email_delivery TO kairos_app;
