-- Supabase Auth 도입.
-- 로그인(NYU Google 계정)과 세션은 Supabase가 관리하고, users 행은 auth_uid(Supabase 유저 UUID)로 연결한다.
-- 비밀번호를 받지 않으므로 password_hash는 비워 둔다.
-- refresh_tokens / auth_tokens 테이블은 더 이상 쓰지 않지만 지우지는 않는다.
-- 적용: ~/miniconda3/envs/eventapp/bin/python scripts/apply_migration.py migrations/001_supabase_auth.sql

ALTER TABLE users
  ADD COLUMN auth_uid CHAR(36) NULL AFTER id,
  ADD UNIQUE KEY uq_users_auth_uid (auth_uid),
  MODIFY password_hash VARCHAR(255) NULL;
