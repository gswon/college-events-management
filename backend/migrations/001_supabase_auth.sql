-- Move authentication to Supabase Auth.
-- Supabase keeps passwords, sessions and verification emails; a users row links to it by auth_uid (the Supabase user UUID).
-- MySQL no longer stores passwords, so password_hash may be empty.
-- The refresh_tokens / auth_tokens tables are no longer used but are kept.
-- Apply: ~/miniconda3/envs/eventapp/bin/python scripts/apply_migration.py migrations/001_supabase_auth.sql

ALTER TABLE users
  ADD COLUMN auth_uid CHAR(36) NULL AFTER id,
  ADD UNIQUE KEY uq_users_auth_uid (auth_uid),
  MODIFY password_hash VARCHAR(255) NULL;
