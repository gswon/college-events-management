from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from errors import register_error_handlers
from routers import categories, events

API_PREFIX = "/api/v1"

app = FastAPI(title="NYU Event Calendar API")

# Expo web 개발용. 인증(쿠키)을 붙일 때 origin을 명시적으로 제한한다.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

register_error_handlers(app)

app.include_router(events.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
