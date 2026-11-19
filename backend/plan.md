# 백엔드 API 남은 작업

- 기준: `NYU 이벤트 캘린더 — DB 스키마 & API 명세.pdf` (엔드포인트 54개)
- 코드 기준: `backend` 브랜치 `ffde944` (2026-11-11)
- 경로는 모두 `/api/v1` 아래

## 현황

| 구분 | 개수 |
|---|---|
| 구현 완료 | 38 |
| 구현됐지만 일부 빠짐 | 0 |
| 미구현 | 16 |

## 우선순위

앱이 돌아가는 데 막히는 순서.

1. [x] `GET /users/me` — 프론트 `src/services/api.ts`가 이미 호출하는데 지금은 404 → 11-18 완료 (`PATCH /users/me`도 함께)
2. [x] `PUT·DELETE /events/{event_id}/save` — 없으면 이벤트를 내 캘린더에 넣을 방법이 없음. 캘린더의 이벤트 표시, 친구 활동이 모두 이 데이터를 씀 → 11-18 완료
3. [x] `GET /users/search` — 친구 요청을 보내려면 상대를 찾아야 함 → 11-18 완료
4. [ ] `/schedule-imports` — 수업 일정을 넣는 유일한 방법 (Albert .ics)
5. 나머지 (아래 목록)

## 미구현 (16개)

### 유저 `/users` (5개 남음)

- [x] `GET /users/me` — 내 정보 (11-18, `routers/users.py`)
- [x] `PATCH /users/me` — display_name, profile_image_url 수정 (11-18). 사진은 http(s) URL만 저장, 파일 업로드는 아직 없음
- [ ] `DELETE /users/me` — 탈퇴. 관련 데이터는 CASCADE 삭제. Supabase 유저 삭제 방법도 정해야 함 (지금은 secret 키가 없음)
- [ ] `GET /users/me/sharing-defaults` — 새 친구에게 적용할 기본 공유 수준
- [ ] `PATCH /users/me/sharing-defaults` — `{class?, personal?, event?, apply_to_existing_friends?}`
- [ ] `GET /users/me/saved-events` — 저장한 이벤트 목록. `?status=GOING&upcoming=true`
- [x] `GET /users/me/following` — 팔로우한 단체 목록 (11-18, 이름순, 페이지 없음)
- [x] `GET /users/search` — `?q=` 이메일 정확 일치 또는 이름 부분 일치, 최대 20명 (11-18). 명세에 더해 `friend_status`를 넣고, 이름 검색은 2자 이상, 다른 사람 이메일은 응답에 안 넣음
- [ ] `GET /users/{user_id}` — 프로필 + friend_status (NONE / REQUESTED / RECEIVED / FRIENDS)

### 이벤트 저장 / 친구 활동 (2개 남음)

- [x] `PUT /events/{event_id}/save` — `{status: INTERESTED | GOING}` 저장 또는 변경 (11-18). 취소된 이벤트는 새로 저장 불가(409 `EVENT_CANCELLED`), 기존 저장은 변경·취소 가능
- [x] `DELETE /events/{event_id}/save` — 저장 취소 (11-18). 저장이 없어도 204
- [ ] `GET /events/{event_id}/friends` — 이 이벤트를 저장한 친구 목록 (status 포함)
- [ ] `GET /events/friends-activity` — 친구들이 저장한 다가오는 이벤트, 친구 수 많은 순

### 단체 `/organizations` (11-18 완료)

- [x] `GET /organizations` — 공개. 목록·검색 `?q&cursor&limit`. 이름순 커서, 명세에 더해 항목마다 `is_following`
- [x] `GET /organizations/{org_id}` — 공개. 상세 + 팔로워 수 + is_following (비로그인은 false)
- [x] `PUT /organizations/{org_id}/follow` — 팔로우. 반복해도 결과 같음, 없는 단체는 404
- [x] `DELETE /organizations/{org_id}/follow` — 언팔로우. 팔로우 안 했어도 204

### Albert 시간표 `/schedule-imports` (3개)

- [ ] `POST /schedule-imports` — multipart .ics 업로드, `term_code?`, `?dry_run=true`면 미리보기만
- [ ] `GET /schedule-imports` — 업로드한 학기 목록
- [ ] `DELETE /schedule-imports/{import_id}` — 해당 학기 수업 일정 전체 삭제

명세의 import 흐름(파싱·UTC 변환·학기 추정·한 트랜잭션 저장)을 따른다. 실제 Albert .ics 파일 하나로 SUMMARY 형식부터 확인해야 course_code 정규식을 정할 수 있다.

### 관리자 `/admin` (6개, ADMIN만)

데이터 팀이 지금 DB에 직접 적재하고 있어 급하지 않다 (명세에도 직접 넣어도 된다고 되어 있음).

- [ ] `POST /admin/events/bulk-upsert` — 최대 500건, (source, external_id) 기준
- [ ] `POST /admin/events` — 수동 등록 (source=MANUAL)
- [ ] `PATCH /admin/events/{event_id}` — 수정
- [ ] `DELETE /admin/events/{event_id}` — status=HIDDEN (소프트 삭제)
- [ ] `POST /admin/organizations/bulk-upsert` — 단체 일괄 적재
- [ ] `PATCH /admin/organizations/{org_id}` — 수정

## 구현됐지만 일부 빠진 것 (모두 완료)

- [x] `GET /events?followed_only=true` — 로그인 기능 전에 만든 임시 코드라 지금은 항상 401. 단체 팔로우 API가 생기면 `organization_follows`로 필터링하도록 바꿔야 함 → 11-18 완료. 팔로우한 단체의 이벤트만, 비로그인은 401
- [x] `GET /events/{event_id}` — 로그인 상태일 때 줘야 하는 `my_save_status`, `friends_going_count`, 친구 미리보기 3명이 없음 → 11-18 완료. 미리보기 필드 이름은 `friends_going`(이름순 최대 3명). GOING이면서 이벤트를 DETAILS로 공유하는 친구만 센다. 로그인 없이 부르면 `null`/`0`/`[]`, 잘못된 토큰은 401

## 구현 완료 (38개)

- 인증 8개: signup, verify-email, verify-email/resend, login, refresh, logout, password/forgot, password/reset
- 유저 5개: `GET·PATCH /users/me`, `PUT /users/me/password`, `GET /users/search`, `GET /users/me/following`
- 단체 4개: `GET /organizations`, `GET /organizations/{org_id}`, `PUT·DELETE /organizations/{org_id}/follow`
- 캘린더 3개: `GET /calendar`, `GET /users/{user_id}/calendar`, `GET /calendar/overlay`
- 내 일정 4개: `POST /entries`, `GET·PATCH·DELETE /entries/{entry_id}`
- 친구 9개: 목록, 끊기, 요청 목록·보내기·수락·거절·취소, 공유 수준 조회·수정
- 이벤트 5개: `GET /events`, `GET /events/{event_id}`, `GET /categories`, `PUT·DELETE /events/{event_id}/save`

## 참고: 명세와 다르게 정한 것

- 인증은 Supabase Auth로 처리한다. 비밀번호·세션·인증 메일은 Supabase가 관리하고, MySQL `users`와는 `auth_uid`로 연결한다 (`migrations/001_supabase_auth.sql`).
- refresh 토큰은 HttpOnly 쿠키 대신 JSON 본문으로 준다 (Expo 앱).
- access 토큰 유효 시간은 Supabase 기본값인 1시간이다 (명세는 15분).
- 인증 메일은 링크 대신 숫자 코드다 (Supabase 템플릿 `{{ .Token }}`).

---

# 코드 리뷰 (2026-11-11)

- 진행 순서
  1. 리뷰: 이 목록을 만드는 단계
  2. 고른 항목만 수정
  3. 주석·에러 메시지를 영어로 바꿈 (동작은 그대로)
- 대상은 `backend/` 코드 전체다. 데이터 팀 공유본인 `NYUEventSchema.sql`과 이 문서는 뺀다.
- 고칠 항목은 제목 앞 `[ ]`에 표시한다.

## 효율

### [x] E1. 겹쳐 보기에서 쿼리가 사람 수만큼 반복됨 — 추천
- **위치:**
  - `routers/calendar.py:111` `calendar_overlay`
  - `:80` `_levels_for`
  - `:28` `_collect_items`
- **문제:** 한 사람마다 친구 관계 1번, 일정 1번, 저장 이벤트 1번을 따로 조회한다. 친구 10명이면 요청 한 번에 쿼리가 약 33번이다. 로컬에서 Railway DB를 쓰면 쿼리마다 왕복 시간이 쌓인다.
- **제안:** 세 가지를 `user_id IN (...)`으로 한 번씩만 조회한 뒤 사람별로 나눈다. 쿼리가 3~4번으로 줄어든다.
- **동작 변화:** 없음. 응답이 같은지 기존 `test_overlay`로 확인한다.
- **위험:** 중간. 공유 수준 계산 로직을 옮기기 때문이다.
- **결과 (11-18):** 친구 수와 상관없이 조회 3번(친구 관계·일정·저장 이벤트). `test_overlay_query_count_does_not_grow_with_friends`로 고정.

### [x] E2. Supabase를 부를 때마다 새 HTTPS 연결을 만듦 — 추천
- **위치:** `supabase_auth.py:72` `httpx.request(...)`
- **문제:** 호출마다 연결 수립(TLS) 시간이 추가로 든다. 비밀번호 변경은 Supabase를 3번 부르므로 그 시간이 3번 든다.
- **제안:** 모듈에 `httpx.Client` 하나를 두고 재사용한다.
- **동작 변화:** 없음. **위험:** 낮음.
- **결과 (11-18):** `supabase_auth._http()`로 연결을 재사용한다. 실제 Supabase 측정(10번씩 중앙값): 매번 새 연결 238ms → 재사용 88ms. 비밀번호 변경처럼 3번 부르면 약 0.45초 줄어든다.

### 확인했지만 지금은 고칠 필요 없는 것
- **이벤트 목록 조회** (`routers/events.py:42`)
  - 이벤트가 2,003건이고, 테이블 전체를 읽어도 실측 약 1ms다 (EXPLAIN ANALYZE, MySQL 9.7).
  - 수만 건 이상 쌓이면 인덱스를 다시 본다.
  - 250일짜리 이벤트도 있어서, "최대 기간"으로 조회 범위의 아래쪽을 자르는 방식은 쓸 수 없다.
- **카테고리 필터의 추가 조회** (`routers/events.py:68`): 쿼리가 1번 더 나가지만 7행짜리 표라 무시해도 된다.
- **비밀번호 변경의 Supabase 호출 3번** (`routers/account.py`): 현재 비밀번호 확인, 변경, 다른 기기 로그아웃. 셋 다 필요하다.
- **DB 연결 `pool_pre_ping`** (`database.py`): 연결을 꺼낼 때마다 확인 쿼리가 1번 더 들지만, Railway가 연결을 자주 끊어서 유지한다.
- **친구 목록, 친구 요청 목록, 내 캘린더:** 이미 쿼리 한두 번으로 끝난다.

## 읽기 쉬움

### [x] R1. `db_dependency`를 라우터 6개가 똑같이 정의 — 추천
- **위치:** `routers/account.py:38`, `calendar.py:18`, `categories.py:13`, `entries.py:16`, `events.py:18`, `friends.py:16`
- **제안:** `database.py`에 한 번만 정의하고 가져다 쓴다. `auth.py`의 `user_dependency`와 같은 방식이다.
- **동작 변화:** 없음. **위험:** 낮음.
- **결과 (11-18):** `database.db_dependency` 하나로 모으고, 라우터마다 남던 안 쓰는 import(`Annotated`, `Depends`, `Session`)도 지웠다.

### [x] R2. 테스트 공통 헬퍼가 `test_events.py` 안에 있음 — 추천
- **위치:** `tests/test_events.py:9` `at`, `:21` `assert_error`. 다른 테스트 파일 5개가 `from tests.test_events import ...`로 가져다 쓴다.
- **문제:** 이벤트 테스트 파일이 다른 테스트의 의존성이 돼서 헬퍼를 찾기 어렵다.
- **제안:**
  - 두 헬퍼를 `tests/conftest.py`로 옮긴다.
  - 쓰이지 않는 상수 `D`(`tests/test_events.py:6`)도 지운다.
- **동작 변화:** 없음. **위험:** 낮음.
- **결과 (11-18):** 두 헬퍼를 `tests/conftest.py`로 옮기고 테스트 6개 파일이 거기서 가져오게 했다. `D` 삭제. 테스트 116개 통과.

### [x] R3. `followed_only`가 로그인해도 401 "로그인이 필요합니다" — 추천
- **위치:** `routers/events.py:56`
- **문제:** 인증 기능 전에 만든 임시 코드라, 지금은 로그인한 사용자도 401 `AUTH_REQUIRED`를 받는다. 프론트가 "로그인이 풀렸다"고 잘못 판단할 수 있다.
- **제안:**
  - 단체 팔로우 API가 생길 때까지는 501 `NOT_IMPLEMENTED`로 바꾸고, `tests/test_events.py:145`도 함께 고친다.
  - 팔로우 API를 만들 때 실제 필터로 교체한다.
- **동작 변화:** 있음 (401 → 501). **위험:** 낮음.
- **결과 (11-18):** 501 `NOT_IMPLEMENTED`로 바꾸고 테스트도 고쳤다. 팔로우 API를 만들 때 실제 필터로 바꾼다.

### [x] R4. 현재 상황과 맞지 않는 주석 — 추천 (3단계 번역 때 같이)
- `main.py:11`: CORS 주석이 "인증(쿠키)을 붙일 때"라고 되어 있다. 실제로는 Bearer 토큰을 쓰고 쿠키는 쓰지 않는다.
- `routers/events.py:57`: "인증이 붙으면"이라고 되어 있는데, 인증은 이미 붙어 있다.
- **제안:** 3단계에서 사실에 맞게 다시 쓴다.
- **결과 (11-18):** CORS 주석은 Bearer 토큰 기준으로, `followed_only` 주석은 R3 내용으로 다시 썼다.

### [x] R5. 공유 수준(HIDDEN/BUSY/DETAILS)이 세 곳에 따로 정의됨 — 선택
- **위치:** `models.py:11` `SHARE_LEVELS`, `schemas.py:184` `ShareLevel`, `routers/calendar.py:24` `LEVEL_RANK`
- **문제:** 낮은 수준부터 높은 수준으로 가는 순서는 `calendar.py`에만 있다. 수준을 하나 추가하면 세 곳을 같이 고쳐야 한다.
- **제안:** `models.SHARE_LEVELS`를 "낮은 순"으로 정한 기준으로 두고, 나머지 두 개는 그걸로 만든다.
- **동작 변화:** 없음. **위험:** 낮음.
- **결과 (11-18):** `models.SHARE_LEVELS`(낮은 순)가 기준이고, `schemas.ShareLevel`과 `calendar.LEVEL_RANK`는 거기서 만든다.

### [x] R6. 모델 별칭이 한 글자 (`E`, `S`, `Ev`, `F`, `R`) — 선택
- **위치:** `routers/calendar.py`, `routers/friends.py`
- **문제:** 특히 `calendar.py`는 한 함수 안에 `E`(일정)와 `Ev`(이벤트)가 같이 나와 헷갈린다.
- **제안:** `Entry`, `Save`, `Event`, `Friendship`, `Request`처럼 풀어 쓴다.
- **동작 변화:** 없음. **위험:** 낮음.
- **결과 (11-18):** `calendar.py`는 E1 때, `friends.py`는 이번에 `Friendship`, `FriendRequest`로 풀어 썼다. 다른 라우터에는 한 글자 별칭이 없다.

### [x] R7. `_collect_items`가 길고 두 가지 일을 함 — E1과 함께
- **위치:** `routers/calendar.py:28` (약 50줄)
- **제안:** "일정을 캘린더 항목으로"와 "저장 이벤트를 캘린더 항목으로"를 두 함수로 나눈다. E1을 하면 자연스럽게 같이 바뀐다.
- **결과 (11-18):** `_entry_items`, `_event_items`로 나누고 `_calendars`가 합친다. 이 파일의 모델 별칭은 이때 `Entry`, `Save`, `Event`처럼 풀어 썼다 (R6 일부).

### [x] R8. "끝 시각이 시작보다 앞인지" 검사 규칙이 두 가지 — 주석만 추가
- **위치:**
  - `timeutil.py:17` `utc_range`: 조회 기간. 끝이 시작보다 반드시 뒤여야 한다.
  - `routers/entries.py:22` `_check_times`: 일정. 끝과 시작이 같아도 된다.
- **제안:** 둘 다 맞는 규칙이지만 이유가 적혀 있지 않다. 3단계에서 주석으로 이유를 적는다.
- **결과 (11-18):** `utc_range`와 `_check_times`에 서로를 가리키는 이유 주석을 달았다.

## 범위 밖이지만 알아 둘 것
- **테스트가 팀 공용 Railway DB에서 돈다** (`tests/conftest.py`).
  - 대부분은 롤백하지만, FULLTEXT 검색 테스트는 실제로 커밋한 뒤 지운다.
  - 그래서 테스트가 중간에 끊기면 `source='PYTEST'` 이벤트가 공용 DB에 남아 앱에 보일 수 있다.
  - Railway 연결이 자주 끊겨 테스트도 자주 실패한다.
  - 나중에 테스트용 DB를 따로 두는 걸 검토한다.

## [x] 3단계: 영어로 바꾸기 (항목 선택 없이 진행)
- **결과 (11-18):** 대상 파일의 한글 0줄. 남은 한 곳은 `tests/test_auth.py:143`의 테스트 입력값 `"Passw0rd 한글"`로, 한글이 특수문자로 안 쳐진다는 걸 확인하려고 일부러 둔 것이다. 테스트 116개 통과.
- **바꾸는 것:**
  - 주석과 docstring
  - API 에러 메시지, 입력 검증 메시지, 로그 문구
  - API 문서에 나오는 파라미터 설명
  - 스크립트 출력, SQL·requirements 주석
  - 테스트 주석
- **바꾸지 않는 것:**
  - 에러 코드 (`AUTH_REQUIRED` 등)
  - API 경로, 필드 이름, DB 스키마
  - `NYUEventSchema.sql`
- **메시지 문구를 확인하는 테스트**(`tests/test_auth.py:150`, 비밀번호 규칙)도 같이 고친다.
- **확인:** 대상 파일에 한글이 0줄인지, 테스트가 전부 통과하는지 본다.
- **영향:** 앱에 보이는 에러 문구가 영어로 바뀐다. 프론트 팀에 알린다.
