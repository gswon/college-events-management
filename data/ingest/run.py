"""수집 실행 진입점.

  python -m ingest.run                          # 기본 소스 (INGEST_SOURCES, 학사일정 제외)
  python -m ingest.run --source all             # 4개 소스 전부
  python -m ingest.run --source athletics,wasserman   # 골라서
  python -m ingest.run --migrate                # 실행 전에 스키마 적용 (Railway 크론에서 사용)
  python -m ingest.run --source academic --dry-run   # DB에 안 넣고 변환 결과만 출력
  python -m ingest.run --force                  # 원본이 안 바뀌어도 전부 다시 변환 (변환 코드 수정 후)

흐름 (소스마다 같음)
  1단계 fetch       : 웹사이트에서 받기            → RawItem 목록
  2단계 save_raw    : raw_events 에 원본 그대로 저장 (바뀐 것만 다음 단계로)
  3단계 normalize   : 공통 Event 형식으로 변환
  4단계 upsert_event: events (+ organizations) 에 저장
  마무리            : 피드에 보인 이벤트는 last_synced_at 갱신, 사라진 미래 이벤트는 CANCELLED 처리,
                      ingest_runs 에 결과 기록
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from dataclasses import asdict

from . import config
from .sources import SOURCES
from .store import Lookup, cancel_missing, finish_run, save_raw, start_run, touch_synced, upsert_event, utc_now

log = logging.getLogger("ingest")


def run_source(conn, slug: str, *, force: bool = False) -> dict:
    module = SOURCES[slug]
    source = module.SOURCE
    counts = {"fetched": 0, "changed": 0, "upserted": 0, "skipped": 0, "canceled": 0}
    started_at = utc_now()

    with conn.cursor() as cur:
        run_id = start_run(cur, source, started_at)
    conn.commit()

    try:
        result = module.fetch()
        counts["fetched"] = len(result.items)
        log.info("[%s] 받은 이벤트 %d건", slug, counts["fetched"])

        lookup = Lookup()
        with conn.cursor() as cur:
            for i, item in enumerate(result.items, start=1):
                changed = save_raw(cur, source, item, started_at)
                if changed:
                    counts["changed"] += 1
                if not (changed or force):
                    continue
                try:
                    event = module.normalize(item.payload)
                    event.external_id = item.external_id
                    event.validate()
                except Exception as exc:
                    counts["skipped"] += 1
                    log.warning("[%s] 변환 실패, 건너뜀 (%s): %s", slug, item.external_id, exc)
                    continue
                upsert_event(cur, source, event, lookup, started_at)
                counts["upserted"] += 1
                if i % config.COMMIT_EVERY == 0:
                    conn.commit()

            touch_synced(cur, source, started_at)
            if result.complete:
                counts["canceled"] = cancel_missing(cur, source, started_at, result.window_end_utc)
            finish_run(cur, run_id, "success", counts)
        conn.commit()
        log.info("[%s] 완료: %s", slug, counts)
        return counts

    except Exception:
        conn.rollback()
        err = traceback.format_exc()
        log.error("[%s] 실패:\n%s", slug, err)
        with conn.cursor() as cur:
            finish_run(cur, run_id, "failed", counts, err)
        conn.commit()
        raise


def dry_run(slug: str, limit: int) -> None:
    """DB 없이 1단계(받기)와 3단계(변환)만 해서 결과를 JSON 으로 출력한다."""
    module = SOURCES[slug]
    result = module.fetch()
    print(f"# {slug}: {len(result.items)}건 받음 (complete={result.complete})", file=sys.stderr)
    for item in result.items[:limit]:
        try:
            event = module.normalize(item.payload)
            event.external_id = item.external_id
            event.validate()
            start_at, end_at = event.resolve_times()
            row = {"source": module.SOURCE, **asdict(event),
                   "db_start_at": start_at.isoformat(), "db_end_at": end_at.isoformat()}
            print(json.dumps(row, ensure_ascii=False, default=str))
        except Exception as exc:
            print(json.dumps({"external_id": item.external_id, "error": str(exc),
                              "payload": item.payload}, ensure_ascii=False, default=str))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NYU 이벤트 수집기")
    parser.add_argument("--source", default=config.DEFAULT_SOURCES,
                        help=f"all 또는 쉼표로 구분한 소스 이름 ({', '.join(SOURCES)}). "
                             f"기본값: {config.DEFAULT_SOURCES}")
    parser.add_argument("--dry-run", action="store_true", help="DB에 저장하지 않고 변환 결과만 출력")
    parser.add_argument("--limit", type=int, default=20, help="--dry-run 때 출력할 최대 건수")
    parser.add_argument("--force", action="store_true", help="원본이 안 바뀌었어도 다시 변환·저장")
    parser.add_argument("--migrate", action="store_true",
                        help="실행 전에 스키마 적용 (INGEST_APPLY_SCHEMA: all / ingest / none)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    slugs = list(SOURCES) if args.source == "all" else [s.strip() for s in args.source.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in SOURCES]
    if unknown or not slugs:
        parser.error(f"알 수 없는 소스: {', '.join(unknown) or '(비어 있음)'} — 가능한 값: all, {', '.join(SOURCES)}")

    if args.dry_run:
        for slug in slugs:
            dry_run(slug, args.limit)
        return 0

    from .db import connect

    failed = []
    conn = connect()
    try:
        if args.migrate:
            from .migrate import apply
            apply(conn, config.APPLY_SCHEMA)
        for slug in slugs:
            try:
                run_source(conn, slug, force=args.force)
            except Exception:
                failed.append(slug)  # 한 소스가 실패해도 나머지는 계속
    finally:
        conn.close()

    if failed:
        log.error("실패한 소스: %s", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
