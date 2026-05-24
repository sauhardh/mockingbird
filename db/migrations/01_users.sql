CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  username    TEXT UNIQUE NOT NULL,
  email       TEXT UNIQUE,
  total_recordings INTEGER DEFAULT 0,
  badges      TEXT[] DEFAULT '{}'
);
