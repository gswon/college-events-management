-- 학교(college) 구분. 데이터팀이 추가한 테이블로, NYUEventSchema.sql(백엔드 원본)은 건드리지 않는다.
-- ingest/migrate.py 가 NYUEventSchema.sql 다음에 적용한다. 여러 번 실행해도 안전하다.
--
-- 이 파일 다음에 migrate.py 가 컬럼이 없을 때만 아래를 추가한다 (MySQL 8 은 ADD COLUMN IF NOT EXISTS 가 없어서 코드로 확인):
--   events.college_id         TINYINT UNSIGNED NOT NULL DEFAULT 1   (FK → colleges.id, 인덱스 college_id, status, start_at)
--   organizations.college_id  TINYINT UNSIGNED NOT NULL DEFAULT 1   (FK → colleges.id)
-- 기본값 1 = NYU 라서, 기존 행과 college_id 를 모르는 INSERT(백엔드의 MANUAL 이벤트 등)는 NYU 로 들어간다.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS colleges (
  id            TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code          VARCHAR(30)     NOT NULL,                        -- 크롤러가 쓰는 키 (NYU, PRINCETON)
  name          VARCHAR(100)    NOT NULL,
  short_name    VARCHAR(50)     NOT NULL,
  location      VARCHAR(100)    NULL,                            -- 'New York, NY'
  timezone      VARCHAR(50)     NOT NULL DEFAULT 'America/New_York',
  website_url   VARCHAR(500)    NULL,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_colleges_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- id 를 고정한다 (events.college_id 기본값 1 = NYU). 이름 등은 다시 실행하면 이 값으로 맞춘다.
INSERT INTO colleges (id, code, name, short_name, location, timezone, website_url) VALUES
  (1, 'NYU',       'New York University',  'NYU',       'New York, NY',  'America/New_York', 'https://www.nyu.edu'),
  (2, 'PRINCETON', 'Princeton University', 'Princeton', 'Princeton, NJ', 'America/New_York', 'https://www.princeton.edu')
AS new
ON DUPLICATE KEY UPDATE
  name = new.name, short_name = new.short_name, location = new.location,
  timezone = new.timezone, website_url = new.website_url;
