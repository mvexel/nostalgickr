import datetime
import json
import secrets

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from requests_oauthlib import OAuth1Session
from starlette.config import Config
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request as StarletteRequest

from flickr_api import FlickrAPI


async def get_oauth_session(request):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    if session_data.get("oauth_token") and session_data.get("oauth_token_secret"):
        return (
            OAuth1Session(
                FLICKR_API_KEY,
                client_secret=FLICKR_API_SECRET,
                resource_owner_key=session_data.get("oauth_token"),
                resource_owner_secret=session_data.get("oauth_token_secret"),
            ),
            session_id,
            session_data,
        )
    return None, session_id, session_data


async def build_template_context(request, extra=None):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    logged_in = bool(
        session_data.get("oauth_token") and session_data.get("oauth_token_secret")
    )
    user_display_name = None
    if logged_in:
        user_info = await flickr.fetch_user_info(
            session_data.get("oauth_token"), session_data.get("oauth_token_secret")
        )
        if user_info:
            user_display_name = user_info.get("username", {}).get("_content")
    ctx = {
        "request": request,
        "logged_in": logged_in,
        "user_display_name": user_display_name,
        "now": datetime.datetime.now(),
    }
    if extra:
        ctx.update(extra)
    return ctx


app = FastAPI()

# Redis client for session and cache
redis_client = redis.from_url("redis://redis:6379/0", decode_responses=True)
SESSION_COOKIE = "session_id"


async def get_session_id(request):
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        session_id = secrets.token_urlsafe(32)
    return session_id


async def get_session_data(session_id):
    data = await redis_client.get(f"session:{session_id}")
    if data:
        return json.loads(data)
    return {}


async def set_session_data(session_id, data):
    await redis_client.set(f"session:{session_id}", json.dumps(data), ex=60 * 60 * 24)


@app.exception_handler(404)
async def custom_404_handler(request: StarletteRequest, exc: StarletteHTTPException):
    import datetime

    return templates.TemplateResponse(
        "404.html",
        {"request": request, "now": datetime.datetime.now()},
        status_code=404,
    )


# Serve static files (CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")


def datetimeformat(value):
    """
    Format a Unix timestamp or date string into a friendly display:
    - Today at HH:MM
    - Yesterday at HH:MM
    - Else: Apr 15, 2025, 21:00

    NOTE: This logic is duplicated in static/main.js (function datetimeformat) for client-side rendering.
    If you modify this function, update the JS version as well to keep formatting consistent across the app.
    """
    try:
        if isinstance(value, int):
            dt = datetime.datetime.fromtimestamp(value)
        elif isinstance(value, str) and value.isdigit():
            dt = datetime.datetime.fromtimestamp(int(value))
        else:
            # Try parsing as string
            try:
                dt = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return value
        now = datetime.datetime.now()
        today = now.date()
        if dt.date() == today:
            return f"Today at {dt.strftime('%-I:%M %p')}"
        elif dt.date() == (today - datetime.timedelta(days=1)):
            return f"Yesterday at {dt.strftime('%-I:%M %p')}"
        else:
            return dt.strftime("%b %-d, %Y, %-I:%M %p")
    except Exception:
        return value


templates.env.filters["datetimeformat"] = datetimeformat

# Load secrets from environment variables
config = Config(".env")
FLICKR_API_KEY = config("FLICKR_API_KEY", cast=str, default="YOUR_FLICKR_API_KEY")
FLICKR_API_SECRET = config(
    "FLICKR_API_SECRET", cast=str, default="YOUR_FLICKR_API_SECRET"
)
CALLBACK_URL = config(
    "CALLBACK_URL", cast=str, default="http://localhost:8000/callback"
)
REDIS_URL = config("REDIS_URL", cast=str, default="redis://redis:6379/0")
REDIS_PHOTO_DETAILS_CACHE_TTL = config(
    "REDIS_PHOTO_DETAILS_CACHE_TTL", cast=int, default=172800
)
REDIS_FRIENDS_CACHE_TTL = config(
    "REDIS_FRIENDS_CACHE_TTL", cast=int, default=60 * 60 * 2
)

REQUEST_TOKEN_URL = "https://www.flickr.com/services/oauth/request_token"
AUTHORIZE_URL = "https://www.flickr.com/services/oauth/authorize"
ACCESS_TOKEN_URL = "https://www.flickr.com/services/oauth/access_token"

flickr = FlickrAPI(FLICKR_API_KEY, FLICKR_API_SECRET)


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    page: int = 1,
    privacy: str = Query(
        "public", enum=["public", "friends", "family", "friendsfamily", "private"]
    ),
):
    photos = []
    pages = 1
    user_nsid = None
    oauth, session_id, session_data = await get_oauth_session(request)
    if oauth:
        user_info = await flickr.fetch_user_info(
            session_data.get("oauth_token"), session_data.get("oauth_token_secret")
        )
        if user_info:
            user_nsid = user_info.get("id")
    if oauth and user_nsid:
        # Map privacy string to Flickr API privacy_filter
        privacy_map = {
            "public": 1,
            "friends": 2,
            "family": 3,
            "friendsfamily": 4,
            "private": 5,
        }
        privacy_filter = privacy_map.get(privacy)
        photos_response = await flickr.fetch_own_photos(
            session_data.get("oauth_token"),
            session_data.get("oauth_token_secret"),
            per_page=20,
            page=page,
            privacy_filter=privacy_filter,
        )
        if photos_response is not None:
            photos = photos_response.get("photos", [])
            pages = photos_response.get("pages", 1)
    context = await build_template_context(
        request,
        {
            "photos": photos,
            "pages": pages,
            "page": page,
            "privacy": privacy,
        },
    )
    resp = templates.TemplateResponse("index.html", context)
    resp.set_cookie(SESSION_COOKIE, await get_session_id(request), httponly=True)
    return resp


@app.get("/photo_details/{photo_id}")
async def photo_details(request: Request, photo_id: str):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    cache_key = f"photo_details:{photo_id}"
    # Try to get cached details
    cached = await redis_client.get(cache_key)
    if cached:
        resp = JSONResponse(json.loads(cached))
        resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
        return resp
    logged_in = session_data.get("oauth_token") is not None
    if logged_in:
        data = await flickr.fetch_photo_details(
            session_data.get("oauth_token"),
            session_data.get("oauth_token_secret"),
            photo_id,
        )
    else:
        # For unauthenticated, fallback to httpx (public info only)
        params = {
            "method": "flickr.photos.getInfo",
            "photo_id": photo_id,
            "format": "json",
            "nojsoncallback": 1,
            "api_key": FLICKR_API_KEY,
        }
        resp = await httpx.AsyncClient().get(
            "https://api.flickr.com/services/rest", params=params
        )
        if resp.status_code != 200:
            return JSONResponse({"error": "Failed to fetch details."}, status_code=500)
        data = resp.json().get("photo", {})
    tags = [t["_content"] for t in data.get("tags", {}).get("tag", [])]
    views = data.get("views")
    comments = data.get("comments", {}).get("_content")
    description = data.get("description", {}).get("_content")
    result = {
        "tags": tags,
        "views": views,
        "comments": comments,
        "description": description,
    }
    await redis_client.set(
        cache_key, json.dumps(result), ex=REDIS_PHOTO_DETAILS_CACHE_TTL
    )
    resp = JSONResponse(result)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.get("/photo/{photo_id}", response_class=HTMLResponse)
async def photo_page(request: Request, photo_id: str):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    logged_in = session_data.get("oauth_token") is not None
    try:
        if logged_in:
            data = await flickr.fetch_photo_details(
                session_data.get("oauth_token"),
                session_data.get("oauth_token_secret"),
                photo_id,
            )
        else:
            # For unauthenticated, fallback to httpx (public info only)
            params = {
                "method": "flickr.photos.getInfo",
                "photo_id": photo_id,
                "format": "json",
                "nojsoncallback": 1,
                "api_key": FLICKR_API_KEY,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.flickr.com/services/rest", params=params
                )
                if resp.status_code != 200:
                    return HTMLResponse(
                        "<h2>Photo not found or error fetching data.</h2>",
                        status_code=404,
                    )
                data = resp.json().get("photo", {})
    except httpx.ConnectError:
        return HTMLResponse(
            "<h2>Unable to connect to Flickr. Please check your internet connection.</h2>",
            status_code=503,
        )
    except Exception as e:
        import logging

        logging.error(f"Error fetching photo details: {str(e)}")
        return HTMLResponse(
            "<h2>An error occurred while fetching photo details.</h2>", status_code=500
        )
    tags = [t["_content"] for t in data.get("tags", {}).get("tag", [])]
    data["tags"] = tags

    # Fetch sizes
    sizes_params = {
        "method": "flickr.photos.getSizes",
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1,
        "api_key": FLICKR_API_KEY,
    }
    sizes_resp = await httpx.AsyncClient().get(
        "https://api.flickr.com/services/rest", params=sizes_params
    )
    image_urls = []
    if sizes_resp.status_code == 200:
        sizes_data = sizes_resp.json().get("sizes", {}).get("size", [])
        # Sort by width descending
        sizes_data.sort(key=lambda x: int(x.get("width", 0)), reverse=True)
    user_display_name = None
    if logged_in:
        user_info = await flickr.fetch_user_info(
            session_data.get("oauth_token"), session_data.get("oauth_token_secret")
        )
        if user_info:
            user_display_name = user_info.get("username", {}).get("_content")
    context = await build_template_context(
        request,
        {
            "photo": data,
            "sizes_data": sizes_data,
            "user_display_name": user_display_name,
        },
    )
    resp = templates.TemplateResponse("photo.html", context)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.get("/login")
async def login(request: Request):
    oauth = OAuth1Session(
        FLICKR_API_KEY,
        client_secret=FLICKR_API_SECRET,
        callback_uri=CALLBACK_URL,
    )
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    session_data["oauth_token"] = fetch_response.get("oauth_token")
    session_data["oauth_token_secret"] = fetch_response.get("oauth_token_secret")
    await set_session_data(session_id, session_data)
    authorization_url = oauth.authorization_url(AUTHORIZE_URL)
    resp = RedirectResponse(authorization_url)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.get("/callback")
async def callback(
    request: Request, oauth_token: str = None, oauth_verifier: str = None
):
    if not oauth_token or not oauth_verifier:
        return RedirectResponse("/")
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    oauth = OAuth1Session(
        FLICKR_API_KEY,
        client_secret=FLICKR_API_SECRET,
        resource_owner_key=session_data.get("oauth_token"),
        resource_owner_secret=session_data.get("oauth_token_secret"),
        verifier=oauth_verifier,
    )
    oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    session_data["oauth_token"] = oauth_tokens.get("oauth_token")
    session_data["oauth_token_secret"] = oauth_tokens.get("oauth_token_secret")
    await set_session_data(session_id, session_data)
    resp = RedirectResponse("/")
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.get("/logout")
async def logout(request: Request):
    session_id = await get_session_id(request)
    await redis_client.delete(f"session:{session_id}")
    resp = RedirectResponse("/")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/friends", response_class=HTMLResponse)
async def friends_photos(request: Request):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    if not (session_data.get("oauth_token") and session_data.get("oauth_token_secret")):
        resp = RedirectResponse("/login")
        resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
        return resp

    friends = await flickr.fetch_contacts(
        session_data.get("oauth_token"), session_data.get("oauth_token_secret")
    )
    if friends is None:
        friends = []
    context = await build_template_context(
        request,
        {
            "friends": friends,
            "page": 1,
        },
    )
    resp = templates.TemplateResponse("friends.html", context)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    if not (session_data.get("oauth_token") and session_data.get("oauth_token_secret")):
        resp = RedirectResponse("/login")
        resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
        return resp

    # Get user NSID (from session or fetch)
    user_nsid = session_data.get("user_nsid")
    if not user_nsid:
        user_info = await flickr.fetch_user_info(
            session_data.get("oauth_token"), session_data.get("oauth_token_secret")
        )
        user_nsid = user_info.get("id") if user_info else None
        if user_nsid:
            session_data["user_nsid"] = user_nsid
            await set_session_data(session_id, session_data)
    if not user_nsid:
        resp = RedirectResponse("/login")
        resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
        return resp

    groups = await flickr.fetch_user_groups(
        session_data.get("oauth_token"),
        session_data.get("oauth_token_secret"),
        user_nsid,
        extras="privacy,throttle,restrictions",
    )
    if groups is None:
        groups = []
    # Decode HTML entities in group names
    import html

    for group in groups:
        if "name" in group:
            group["name"] = html.unescape(group["name"])
    context = await build_template_context(
        request,
        {
            "groups": groups,
        },
    )
    resp = templates.TemplateResponse("groups.html", context)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.post("/friend_latest_photos")
async def friend_latest_photos(request: Request, nsids: list = Body(...)):
    """
    Fetch latest photos for a list of friends using contacts photos API.
    Uses Redis cache for better performance.
    Returns basic photo info without sizes (those are fetched separately).
    """
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    session_oauth_token = session_data.get("oauth_token")
    session_oauth_secret = session_data.get("oauth_token_secret")
    if not (session_oauth_token and session_oauth_secret):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        # Try to get cached contacts photos first
        cache_key = "contacts_photos"
        cached = await redis_client.get(cache_key)
        if cached:
            contacts_photos = json.loads(cached)
        else:
            contacts_photos = await flickr.fetch_contacts_photos(
                session_oauth_token,
                session_oauth_secret,
                count=50,
                single_photo=True,
                just_friends=False,
                extras="date_upload,date_taken,owner_name,icon_server,icon_farm",
            )
            if contacts_photos is None:
                return JSONResponse(
                    {"error": "Failed to fetch contacts photos"}, status_code=500
                )
            # Cache for 2 hours
            await redis_client.set(
                cache_key, json.dumps(contacts_photos), ex=REDIS_FRIENDS_CACHE_TTL
            )

        photo_map = {photo["owner"]: photo for photo in contacts_photos}

        out = {}
        for nsid in nsids:
            if nsid in photo_map:
                out[nsid] = photo_map[nsid]
            else:
                out[nsid] = {"error": "No photo found"}
    except httpx.ConnectError:
        return JSONResponse(
            {
                "error": "Unable to connect to Flickr. Please check your internet connection."
            },
            status_code=503,
        )
    except Exception as e:
        import logging

        logging.error(f"Error in friend_latest_photos: {str(e)}")
        return JSONResponse(
            {"error": "An error occurred while fetching photos"}, status_code=500
        )

    resp = JSONResponse(out)
    resp.set_cookie(SESSION_COOKIE, session_id, httponly=True)
    return resp


@app.post("/batch_photo_sizes")
async def batch_photo_sizes(request: Request, photo_ids: list = Body(...)):
    """
    Fetch sizes for multiple photos in parallel with caching.
    """
    session_id = await get_session_id(request)
    session_data = await get_session_data(session_id)
    session_oauth_token = session_data.get("oauth_token")
    session_oauth_secret = session_data.get("oauth_token_secret")
    if not (session_oauth_token and session_oauth_secret):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        # Try to get cached sizes first
        cached_sizes = {}
        uncached_ids = []
        for photo_id in photo_ids:
            cache_key = f"photo_sizes:{photo_id}"
            cached = await redis_client.get(cache_key)
            if cached:
                cached_sizes[photo_id] = json.loads(cached)
            else:
                uncached_ids.append(photo_id)

        # Fetch uncached sizes in parallel
        if uncached_ids:
            import asyncio

            tasks = []
            for photo_id in uncached_ids:
                tasks.append(
                    flickr.fetch_photo_sizes(
                        session_oauth_token, session_oauth_secret, photo_id
                    )
                )
            results = await asyncio.gather(*tasks)

            # Cache results and build response
            for photo_id, sizes in zip(uncached_ids, results):
                if sizes:
                    # Cache for 1 week since sizes don't change
                    await redis_client.set(
                        f"photo_sizes:{photo_id}",
                        json.dumps(sizes),
                        ex=60 * 60 * 24 * 7,
                    )
                    cached_sizes[photo_id] = sizes

        return JSONResponse(cached_sizes)
    except Exception as e:
        import logging

        logging.error(f"Error in batch_photo_sizes: {str(e)}")
        return JSONResponse(
            {"error": "An error occurred while fetching photo sizes"}, status_code=500
        )
