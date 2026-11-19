"""소스 레지스트리. 새 소스를 추가하려면 같은 모양(SLUG, SOURCE, COLLEGE, NAME, BASE_URL, fetch, normalize)의
모듈을 만들고 여기에 등록하면 된다.
COLLEGE 는 colleges.code (NYU / PRINCETON) — events.college_id 가 된다.
SOURCE 는 events.source / raw_events.source 에 들어가는 대문자 코드 (예: NYU_EVENTS)."""
from . import academic, athletics, nyu_events, princeton_athletics, princeton_events, technyu, wasserman

SOURCES = {
    nyu_events.SLUG: nyu_events,
    wasserman.SLUG: wasserman,
    athletics.SLUG: athletics,
    academic.SLUG: academic,
    technyu.SLUG: technyu,
    princeton_events.SLUG: princeton_events,
    princeton_athletics.SLUG: princeton_athletics,
}
