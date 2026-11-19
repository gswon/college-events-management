# Railway(또는 아무 Docker 호스트)에서 수집기를 한 번 실행하고 종료하는 이미지.
# Railway 크론이 정해진 시각마다 이 컨테이너를 띄운다 (railway.json 의 cronSchedule).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY NYUEventSchema.sql schema_ingest.sql schema_colleges.sql ./
COPY ingest ./ingest

RUN useradd --create-home --uid 10001 ingest
USER ingest

# --migrate: 없는 테이블만 만든다 (INGEST_APPLY_SCHEMA=all|ingest|none 으로 조절)
# --migrate 는 colleges 테이블과 events/organizations.college_id 컬럼도 (없을 때만) 추가한다
# 소스 목록은 INGEST_SOURCES (기본: NYU 4개 + princeton_events,princeton_athletics — 학사일정은 수동)
CMD ["python", "-m", "ingest.run", "--migrate"]
