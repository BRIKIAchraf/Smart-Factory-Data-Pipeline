CREATE TABLE IF NOT EXISTS machine_events (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50),
    status VARCHAR(20),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_machine_id ON machine_events(machine_id);
