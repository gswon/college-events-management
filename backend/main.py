from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from errors import register_error_handlers
from routers import account, calendar, categories, entries, events, friends, organizations, users

API_PREFIX = "/api/v1"

app = FastAPI(title="NYU Event Calendar API")

# Any origin is allowed for Expo web development. Auth uses Bearer tokens, not cookies,
# so no session rides along with cross-site requests. List the real app origins before deploying.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

register_error_handlers(app)

app.include_router(account.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
app.include_router(organizations.router, prefix=API_PREFIX)
app.include_router(entries.router, prefix=API_PREFIX)
app.include_router(calendar.router, prefix=API_PREFIX)
app.include_router(friends.router, prefix=API_PREFIX)
