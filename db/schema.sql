CREATE TABLE tickets (
    id bigserial PRIMARY KEY,
    title varchar(200) NOT NULL CHECK (length(trim(title)) > 0),
    status varchar(16) NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE outbox (
    id uuid PRIMARY KEY,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX outbox_pending ON outbox(created_at) WHERE published_at IS NULL;
CREATE TABLE processed_events (event_id uuid PRIMARY KEY, processed_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE notifications (
    id bigserial PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    ticket_id bigint NOT NULL,
    message text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;
