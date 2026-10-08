-- =====================================================================
-- NYU Event Calendar — MySQL 8.0 schema
-- 모든 DATETIME 컬럼은 UTC 기준. 표시용 변환(America/New_York)은 프론트에서.
-- =====================================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS nyu_calendar
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE nyu_calendar;

-- ---------------------------------------------------------------------
-- 1. 유저 / 인증
-- ---------------------------------------------------------------------

CREATE TABLE users (
  id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email                   VARCHAR(255)    NOT NULL,              -- @nyu.edu 제한은 앱에서 검사
  password_hash           VARCHAR(255)    NOT NULL,              -- argon2 / bcrypt
  display_name            VARCHAR(50)     NOT NULL,
  profile_image_url       VARCHAR(500)    NULL,
  role                    ENUM('USER','ADMIN') NOT NULL DEFAULT 'USER',
  -- 새 친구가 생길 때 friendships 행으로 복사되는 기본 공유 수준
  default_share_class     ENUM('HIDDEN','BUSY','DETAILS') NOT NULL DEFAULT 'DETAILS',
  default_share_personal  ENUM('HIDDEN','BUSY','DETAILS') NOT NULL DEFAULT 'BUSY',
  default_share_event     ENUM('HIDDEN','BUSY','DETAILS') NOT NULL DEFAULT 'DETAILS',
  email_verified_at       DATETIME        NULL,
  created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_display_name (display_name)
) ENGINE=InnoDB;

CREATE TABLE refresh_tokens (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id       BIGINT UNSIGNED NOT NULL,
  token_hash    CHAR(64)        NOT NULL,                        -- SHA-256 hex, 원문 저장 금지
  user_agent    VARCHAR(255)    NULL,
  expires_at    DATETIME        NOT NULL,
  revoked_at    DATETIME        NULL,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_refresh_tokens_hash (token_hash),
  KEY idx_refresh_tokens_user (user_id),
  CONSTRAINT fk_refresh_tokens_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE auth_tokens (                                       -- 이메일 인증 / 비밀번호 재설정
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id       BIGINT UNSIGNED NOT NULL,
  purpose       ENUM('VERIFY_EMAIL','RESET_PASSWORD') NOT NULL,
  token_hash    CHAR(64)        NOT NULL,
  expires_at    DATETIME        NOT NULL,
  used_at       DATETIME        NULL,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_auth_tokens_hash (token_hash),
  KEY idx_auth_tokens_user_purpose (user_id, purpose),
  CONSTRAINT fk_auth_tokens_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. 이벤트 (학교 공용 데이터)
-- ---------------------------------------------------------------------

CREATE TABLE event_categories (
  id            TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code          VARCHAR(30)     NOT NULL,                        -- 크롤러가 매핑에 쓰는 키
  name          VARCHAR(50)     NOT NULL,
  color         CHAR(7)         NULL,                            -- '#RRGGBB'
  sort_order    TINYINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uq_event_categories_code (code)
) ENGINE=InnoDB;

CREATE TABLE organizations (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name              VARCHAR(200)    NOT NULL,
  slug              VARCHAR(200)    NOT NULL,
  description       TEXT            NULL,
  website_url       VARCHAR(500)    NULL,
  instagram_handle  VARCHAR(100)    NULL,
  logo_url          VARCHAR(500)    NULL,
  source            VARCHAR(50)     NULL,                        -- 크롤링 출처 (ENGAGE 등)
  external_id       VARCHAR(255)    NULL,
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_organizations_slug (slug),
  UNIQUE KEY uq_organizations_source_ext (source, external_id),
  FULLTEXT KEY ft_organizations_name (name)
) ENGINE=InnoDB;

CREATE TABLE organization_follows (
  user_id          BIGINT UNSIGNED NOT NULL,
  organization_id  BIGINT UNSIGNED NOT NULL,
  created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, organization_id),
  KEY idx_org_follows_org (organization_id),
  CONSTRAINT fk_org_follows_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_org_follows_org FOREIGN KEY (organization_id)
    REFERENCES organizations (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE events (
  id                BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  -- 출처 / upsert 키
  source            VARCHAR(50)      NOT NULL,                   -- 'ENGAGE', 'NYU_EVENTS', 'MANUAL', ...
  external_id       VARCHAR(255)     NULL,                       -- 출처 사이트의 ID (MANUAL이면 NULL)
  source_url        VARCHAR(500)     NULL,
  -- 내용
  title             VARCHAR(255)     NOT NULL,
  description       TEXT             NULL,
  category_id       TINYINT UNSIGNED NOT NULL,
  organization_id   BIGINT UNSIGNED  NULL,
  host_name         VARCHAR(200)     NULL,                       -- 원문 주최자 이름 그대로
  -- 시간 (UTC)
  start_at          DATETIME         NOT NULL,
  end_at            DATETIME         NOT NULL,                   -- 원문에 없으면 start_at + 1h
  is_all_day        BOOLEAN          NOT NULL DEFAULT FALSE,
  -- 장소
  location_name     VARCHAR(255)     NULL,
  address           VARCHAR(255)     NULL,
  is_online         BOOLEAN          NOT NULL DEFAULT FALSE,
  online_url        VARCHAR(500)     NULL,
  -- 부가 정보
  registration_url  VARCHAR(500)     NULL,
  image_url         VARCHAR(500)     NULL,
  is_free           BOOLEAN          NULL,                       -- NULL = 모름
  price_text        VARCHAR(100)     NULL,
  audience_text     VARCHAR(255)     NULL,
  -- 상태
  status            ENUM('ACTIVE','CANCELLED','HIDDEN') NOT NULL DEFAULT 'ACTIVE',
  last_synced_at    DATETIME         NULL,
  created_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_events_source_ext (source, external_id),
  KEY idx_events_start (status, start_at),
  KEY idx_events_category_start (category_id, start_at),
  KEY idx_events_org_start (organization_id, start_at),
  FULLTEXT KEY ft_events_text (title, description),
  CONSTRAINT chk_events_time CHECK (end_at >= start_at),
  CONSTRAINT fk_events_category FOREIGN KEY (category_id)
    REFERENCES event_categories (id),
  CONSTRAINT fk_events_org FOREIGN KEY (organization_id)
    REFERENCES organizations (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE event_saves (                                       -- 저장 = 내 캘린더에 표시
  user_id     BIGINT UNSIGNED NOT NULL,
  event_id    BIGINT UNSIGNED NOT NULL,
  status      ENUM('INTERESTED','GOING') NOT NULL DEFAULT 'INTERESTED',
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, event_id),
  KEY idx_event_saves_event (event_id, status),                  -- "친구 N명이 가요" 조회용
  CONSTRAINT fk_event_saves_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_event_saves_event FOREIGN KEY (event_id)
    REFERENCES events (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. 내 일정 (Albert 수업 + 개인 일정)
-- ---------------------------------------------------------------------

CREATE TABLE schedule_imports (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            BIGINT UNSIGNED NOT NULL,
  term_code          VARCHAR(10)     NOT NULL,                   -- 예: '2026FA'
  original_filename  VARCHAR(255)    NULL,
  entry_count        INT UNSIGNED    NOT NULL DEFAULT 0,
  imported_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_schedule_imports_user_term (user_id, term_code), -- 같은 학기 재업로드 = 덮어쓰기
  CONSTRAINT fk_schedule_imports_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE calendar_entries (
  id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id              BIGINT UNSIGNED NOT NULL,
  kind                 ENUM('CLASS','PERSONAL') NOT NULL,
  schedule_import_id   BIGINT UNSIGNED NULL,                     -- CLASS만 (앱에서 보장)
  title                VARCHAR(255)    NOT NULL,
  description          TEXT            NULL,
  location             VARCHAR(255)    NULL,
  start_at             DATETIME        NOT NULL,
  end_at               DATETIME        NOT NULL,
  is_all_day           BOOLEAN         NOT NULL DEFAULT FALSE,
  color                CHAR(7)         NULL,
  course_code          VARCHAR(50)     NULL,                     -- 예: 'CSCI-UA 202'
  ics_uid              VARCHAR(255)    NULL,                     -- 원본 .ics UID
  -- 친구 공유 수준을 이 항목만 더 낮춤. NULL = 친구 설정 그대로
  visibility_override  ENUM('HIDDEN','BUSY') NULL,
  created_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_entries_user_start (user_id, start_at),
  KEY idx_entries_import (schedule_import_id),
  CONSTRAINT chk_entries_time CHECK (end_at >= start_at),
  CONSTRAINT fk_entries_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_entries_import FOREIGN KEY (schedule_import_id)
    REFERENCES schedule_imports (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. 친구 / 공유
-- ---------------------------------------------------------------------

CREATE TABLE friend_requests (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  from_user_id  BIGINT UNSIGNED NOT NULL,
  to_user_id    BIGINT UNSIGNED NOT NULL,                        -- from <> to 는 앱에서 검사
  status        ENUM('PENDING','ACCEPTED','DECLINED','CANCELLED') NOT NULL DEFAULT 'PENDING',
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  responded_at  DATETIME        NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_friend_requests_pair (from_user_id, to_user_id), -- 재요청은 status를 PENDING으로 갱신
  KEY idx_friend_requests_to (to_user_id, status),
  CONSTRAINT fk_friend_requests_from FOREIGN KEY (from_user_id)
    REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_friend_requests_to FOREIGN KEY (to_user_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 친구 1쌍 = 2행. 행 (user_id=A, friend_id=B) 는 "A가 B에게 공유하는 수준".
CREATE TABLE friendships (
  user_id         BIGINT UNSIGNED NOT NULL,
  friend_id       BIGINT UNSIGNED NOT NULL,
  share_class     ENUM('HIDDEN','BUSY','DETAILS') NOT NULL,
  share_personal  ENUM('HIDDEN','BUSY','DETAILS') NOT NULL,
  share_event     ENUM('HIDDEN','BUSY','DETAILS') NOT NULL,
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, friend_id),
  KEY idx_friendships_friend (friend_id),
  CONSTRAINT fk_friendships_user FOREIGN KEY (user_id)
    REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_friendships_friend FOREIGN KEY (friend_id)
    REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. 초기 데이터
-- ---------------------------------------------------------------------

INSERT INTO event_categories (code, name, color, sort_order) VALUES
  ('SOCIAL',   'Social',             '#F59E0B', 1),
  ('CAREER',   'Career',             '#3B82F6', 2),
  ('SPORTS',   'Sports',             '#10B981', 3),
  ('ACADEMIC', 'Academic',           '#8B5CF6', 4),
  ('ARTS',     'Arts & Culture',     '#EC4899', 5),
  ('WELLNESS', 'Health & Wellness',  '#14B8A6', 6),
  ('OTHER',    'Other',              '#6B7280', 7);

-- =====================================================================
-- 참고 쿼리
-- =====================================================================

-- (a) 내 통합 캘린더: :me, :start, :end
--   SELECT 'EVENT' AS type, e.id, e.title, e.start_at, e.end_at
--   FROM event_saves s JOIN events e ON e.id = s.event_id
--   WHERE s.user_id = :me AND e.status <> 'HIDDEN'
--     AND e.start_at < :end AND e.end_at > :start
--   UNION ALL
--   SELECT c.kind, c.id, c.title, c.start_at, c.end_at
--   FROM calendar_entries c
--   WHERE c.user_id = :me AND c.start_at < :end AND c.end_at > :start;

-- (b) 이벤트 :event_id 에 가는, 나(:me)에게 이벤트를 공개한 친구들
--   SELECT u.id, u.display_name, s.status
--   FROM event_saves s
--   JOIN friendships f ON f.user_id = s.user_id AND f.friend_id = :me
--   JOIN users u ON u.id = s.user_id
--   WHERE s.event_id = :event_id AND f.share_event = 'DETAILS';
