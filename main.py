import os
from fastapi import FastAPI, Request, Response, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from requests_oauthlib import OAuth1Session
import httpx

def get_oauth_session(request):
    """Return an authenticated OAuth1Session if the user is logged in, else None."""
    if request.session.get("oauth_token") and request.session.get("oauth_token_secret"):
        return OAuth1Session(
            FLICKR_API_KEY,
            client_secret=FLICKR_API_SECRET,
            resource_owner_key=request.session.get("oauth_token"),
            resource_owner_secret=request.session.get("oauth_token_secret")
        )
    return None

def build_template_context(request, extra=None):
    """
    Returns a dict of all variables that should be available to every template.
    Pass any additional variables in the 'extra' dict.
    """
    logged_in = bool(request.session.get("oauth_token") and request.session.get("oauth_token_secret"))
    user_display_name = None
    if logged_in:
        oauth = get_oauth_session(request)
        if oauth:
            resp = oauth.get("https://api.flickr.com/services/rest", params={
                "method": "flickr.test.login",
                "format": "json",
                "nojsoncallback": 1,
            })
            if resp.ok:
                user_info = resp.json().get("user", {})
                user_display_name = (
                    (user_info.get("realname") or {}).get("_content")
                    or (user_info.get("username") or {}).get("_content")
                    or user_info.get("nsid")
                )
    context = {
        "request": request,
        "logged_in": logged_in,
        "user_display_name": user_display_name,
        "now": datetime.datetime.now(),
    }
    if extra:
        context.update(extra)
    return context
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Serve static files (CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

import datetime
# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

def datetimeformat(value):
    """
    Format a Unix timestamp or date string into a friendly display:
    - Today at HH:MM
    - Yesterday at HH:MM
    - Else: Apr 15, 2025, 21:00
    """
    import datetime
    try:
        if isinstance(value, int):
            dt = datetime.datetime.fromtimestamp(value)
        elif isinstance(value, str) and value.isdigit():
            dt = datetime.datetime.fromtimestamp(int(value))
        else:
            # Try parsing as string
            try:
                dt = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return value
        now = datetime.datetime.now()
        today = now.date()
        if dt.date() == today:
            return f"Today at {dt.strftime('%-I:%M %p')}"
        elif dt.date() == (today - datetime.timedelta(days=1)):
            return f"Yesterday at {dt.strftime('%-I:%M %p')}"
        else:
            return dt.strftime('%b %-d, %Y, %-I:%M %p')
    except Exception:
        return value


templates.env.filters['datetimeformat'] = datetimeformat

# Load secrets from environment variables (user must set these)
config = Config(".env")
FLICKR_API_KEY = config("FLICKR_API_KEY", cast=str, default="YOUR_FLICKR_API_KEY")
FLICKR_API_SECRET = config("FLICKR_API_SECRET", cast=str, default="YOUR_FLICKR_API_SECRET")
CALLBACK_URL = config("CALLBACK_URL", cast=str, default="http://localhost:8000/callback")

app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET_KEY", "supersecret"))

REQUEST_TOKEN_URL = "https://www.flickr.com/services/oauth/request_token"
AUTHORIZE_URL = "https://www.flickr.com/services/oauth/authorize"
ACCESS_TOKEN_URL = "https://www.flickr.com/services/oauth/access_token"

@app.get("/", response_class=HTMLResponse)
def index(request: Request, page: int = 1, privacy: str = Query("public", enum=["public", "friends", "family", "friendsfamily", "private"])):
    photos = []
    pages = 1
    user_nsid = None
    if request.session.get("oauth_token") and request.session.get("oauth_token_secret"):
        oauth = get_oauth_session(request)
        if oauth:
            # Get user NSID
            resp = oauth.get("https://api.flickr.com/services/rest", params={
                "method": "flickr.test.login",
                "format": "json",
                "nojsoncallback": 1,
            })
            if resp.ok:
                user_info = resp.json().get("user", {})
                user_nsid = user_info.get("id")
            # Fetch user's photos if NSID available
            if user_nsid:
                photo_params = {
                    "method": "flickr.people.getPhotos",
                    "user_id": user_nsid,
                    "per_page": 20,
                    "page": page,
                    "privacy_filter": 1 if privacy == "public" else 5,  # 1=public, 5=all (you may want to adjust)
                    "extras": "url_q,date_upload,date_taken,description,owner_name,title",
                    "format": "json",
                    "nojsoncallback": 1,
                }
                photo_resp = oauth.get("https://api.flickr.com/services/rest", params=photo_params)
                if photo_resp.ok:
                    data = photo_resp.json().get("photos", {})
                    photos = data.get("photo", [])
                    pages = data.get("pages", 1)
    else:
        # Fetch public photos as before
        params = {
            "method": "flickr.photos.getRecent",
            "per_page": 20,
            "page": page,
            "format": "json",
            "nojsoncallback": 1,
            "extras": "url_q,date_upload,date_taken,description,owner_name,title",
        }
        resp = httpx.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
        if resp.status_code == 200:
            data = resp.json().get("photos", {})
            photos = data.get("photo", [])
            pages = data.get("pages", 1)
    context = build_template_context(request, {
        "photos": photos,
        "pages": pages,
        "page": page,
        "privacy": privacy,
    })
    return templates.TemplateResponse("index.html", context)

@app.get("/photo/{photo_id}", response_class=HTMLResponse)
def photo_page(request: Request, photo_id: str):
    params = {
        "method": "flickr.photos.getInfo",
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1,
        "extras": "url_l,url_q,url_m,date_upload,date_taken,description,owner_name,title"
    }
    if request.session.get("oauth_token") and request.session.get("oauth_token_secret"):
        oauth = get_oauth_session(request)
        resp = oauth.get("https://api.flickr.com/services/rest", params=params)
    else:
        resp = httpx.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
    if resp.status_code != 200:
        return HTMLResponse("<h2>Photo not found or error fetching data.</h2>", status_code=404)
    data = resp.json().get("photo", {})
    tags = [t["_content"] for t in data.get("tags", {}).get("tag", [])]
    data["tags"] = tags
    context = build_template_context(request, {"photo": data})
    return templates.TemplateResponse("photo.html", context)

@app.get("/photo_details/{photo_id}")
def photo_details(request: Request, photo_id: str):
    logged_in = request.session.get("oauth_token") is not None
    params = {
        "method": "flickr.photos.getInfo",
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1
    }
    if logged_in:
        oauth = OAuth1Session(
            FLICKR_API_KEY,
            client_secret=FLICKR_API_SECRET,
            resource_owner_key=request.session.get("oauth_token"),
            resource_owner_secret=request.session.get("oauth_token_secret")
        )
        resp = oauth.get("https://api.flickr.com/services/rest", params=params)
    else:
        resp = httpx.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
    if resp.status_code != 200:
        return JSONResponse({"error": "Failed to fetch details."}, status_code=500)
    data = resp.json().get("photo", {})
    tags = [t["_content"] for t in data.get("tags", {}).get("tag", [])]
    views = data.get("views")
    comments = data.get("comments", {}).get("_content")
    description = data.get("description", {}).get("_content")
    return JSONResponse({
        "tags": tags,
        "views": views,
        "comments": comments,
        "description": description
    })

@app.get("/photo/{photo_id}", response_class=HTMLResponse)
def photo_page(request: Request, photo_id: str):
    logged_in = request.session.get("oauth_token") is not None
    params = {
        "method": "flickr.photos.getInfo",
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1,
        "extras": "url_l,url_q,url_m,date_upload,date_taken,description,owner_name,title"
    }
    if logged_in:
        oauth = OAuth1Session(
            FLICKR_API_KEY,
            client_secret=FLICKR_API_SECRET,
            resource_owner_key=request.session.get("oauth_token"),
            resource_owner_secret=request.session.get("oauth_token_secret")
        )
        resp = oauth.get("https://api.flickr.com/services/rest", params=params)
    else:
        resp = httpx.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
    if resp.status_code != 200:
        return HTMLResponse("<h2>Photo not found or error fetching data.</h2>", status_code=404)
    data = resp.json().get("photo", {})
    tags = [t["_content"] for t in data.get("tags", {}).get("tag", [])]
    data["tags"] = tags

    # Fetch sizes
    sizes_params = {
        "method": "flickr.photos.getSizes",
        "photo_id": photo_id,
        "format": "json",
        "nojsoncallback": 1,
        "api_key": FLICKR_API_KEY
    }
    sizes_resp = httpx.get("https://api.flickr.com/services/rest", params=sizes_params)
    image_url = None
    if sizes_resp.status_code == 200:
        sizes_data = sizes_resp.json().get("sizes", {}).get("size", [])
        # Prefer order: Original, Large, Medium 800, Medium 640, Medium, Small
        preferred = ["Original", "Large", "Medium 800", "Medium 640", "Medium", "Small"]
        for label in preferred:
            for size in sizes_data:
                if size.get("label") == label:
                    image_url = size.get("source")
                    break
            if image_url:
                break
        # Fallback: first available
        if not image_url and sizes_data:
            image_url = sizes_data[-1].get("source") 
    # Get user display name if logged in
    user_display_name = None
    if logged_in:
        params = {
            "method": "flickr.test.login",
            "format": "json",
            "nojsoncallback": 1,
            "api_key": FLICKR_API_KEY
        }
        oauth = OAuth1Session(
            FLICKR_API_KEY,
            client_secret=FLICKR_API_SECRET,
            resource_owner_key=request.session.get("oauth_token"),
            resource_owner_secret=request.session.get("oauth_token_secret")
        )
        resp = oauth.get("https://api.flickr.com/services/rest", params=params)
        if resp.ok:
            user_info = resp.json().get("user", {})
            user_display_name = user_info.get("realname") or user_info.get("username") or user_info.get("nsid")
    return templates.TemplateResponse("photo.html", {
        "request": request,
        "photo": data,
        "image_url": image_url,
        "user_display_name": user_display_name,
        "now": datetime.datetime.now()
    })

@app.get("/login")
def login(request: Request):
    oauth = OAuth1Session(
        FLICKR_API_KEY,
        client_secret=FLICKR_API_SECRET,
        callback_uri=CALLBACK_URL
    )
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    request.session["resource_owner_key"] = fetch_response.get("oauth_token")
    request.session["resource_owner_secret"] = fetch_response.get("oauth_token_secret")
    authorization_url = oauth.authorization_url(AUTHORIZE_URL, perms="read")
    return RedirectResponse(authorization_url)

@app.get("/callback")
def callback(request: Request):
    oauth_token = request.query_params.get("oauth_token")
    oauth_verifier = request.query_params.get("oauth_verifier")
    resource_owner_key = request.session.get("resource_owner_key")
    resource_owner_secret = request.session.get("resource_owner_secret")
    if not (oauth_token and oauth_verifier and resource_owner_key and resource_owner_secret):
        return RedirectResponse("/")
    oauth = OAuth1Session(
        FLICKR_API_KEY,
        client_secret=FLICKR_API_SECRET,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=oauth_verifier
    )
    oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    request.session["oauth_token"] = oauth_tokens["oauth_token"]
    request.session["oauth_token_secret"] = oauth_tokens["oauth_token_secret"]
    return RedirectResponse("/")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
