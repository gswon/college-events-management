-- 데이터팀(수집기) 내부 테이블. 백엔드는 쓰지 않는다.
-- NYUEventSchema.sql 다음에 적용한다. 여러 번 실행해도 안전하다.

SET NAMES utf8mb4;

-- 소스에서 받은 원본을 그대로 보관 (소스·이벤트당 최신본 1줄).
-- (source, external_id) 는 events 의 같은 키와 1:1 로 대응한다.
CREATE TABLE IF NOT EXISTS raw_events (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source         VARCHAR(50)     NOT NULL,
  external_id    VARCHAR(255)    NOT NULL,
  payload        JSON            NOT NULL,
  payload_hash   CHAR(64)        NOT NULL,   -- sha256(payload). 비어 있으면 '다음에 무조건 다시 변환'
  first_seen_at  DATETIME(6)     NOT NULL,
  last_seen_at   DATETIME(6)     NOT NULL,   -- 마지막으로 피드에서 본 시각 (사라진 이벤트 감지)
  fetched_at     DATETIME(6)     NOT NULL,   -- payload 가 마지막으로 바뀐 시각
  PRIMARY KEY (id),
  UNIQUE KEY uq_raw_source_ext (source, external_id),
  KEY idx_raw_source_seen (source, last_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 수집 실행 기록 (모니터링용)
CREATE TABLE IF NOT EXISTS ingest_runs (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source          VARCHAR(50)     NOT NULL,
  started_at      DATETIME(6)     NOT NULL,
  finished_at     DATETIME(6)     NULL,
  status          ENUM('running','success','failed') NOT NULL DEFAULT 'running',
  fetched_count   INT UNSIGNED    NOT NULL DEFAULT 0,  -- 소스에서 받은 건수
  changed_count   INT UNSIGNED    NOT NULL DEFAULT 0,  -- 새로 생기거나 바뀐 원본 건수
  upserted_count  INT UNSIGNED    NOT NULL DEFAULT 0,  -- events 에 반영한 건수
  skipped_count   INT UNSIGNED    NOT NULL DEFAULT 0,  -- 변환 실패로 건너뛴 건수
  canceled_count  INT UNSIGNED    NOT NULL DEFAULT 0,  -- 피드에서 사라져 CANCELLED 처리한 건수
  error           TEXT            NULL,
  PRIMARY KEY (id),
  KEY idx_runs_source_started (source, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
