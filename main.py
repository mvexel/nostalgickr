import os
from fastapi import FastAPI, Request, Response, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from requests_oauthlib import OAuth1Session
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

import requests
from fastapi.responses import JSONResponse

@app.get("/", response_class=HTMLResponse)
def index(request: Request, page: int = 1, privacy: str = Query("public", enum=["public", "friends", "family", "friendsfamily", "private"])):
    logged_in = request.session.get("oauth_token") is not None
    photos = []
    pages = 1
    user_nsid = None
    if logged_in:
        # Get user NSID
        oauth = OAuth1Session(
            FLICKR_API_KEY,
            client_secret=FLICKR_API_SECRET,
            resource_owner_key=request.session.get("oauth_token"),
            resource_owner_secret=request.session.get("oauth_token_secret")
        )
        resp = oauth.get("https://api.flickr.com/services/rest", params={
            "method": "flickr.test.login",
            "format": "json",
            "nojsoncallback": 1,
        })
        if resp.ok:
            user_nsid = resp.json().get("user", {}).get("id")
        # Privacy filter mapping per Flickr docs
        privacy_filter_map = {
            "public": 1,
            "friends": 2,
            "family": 3,
            "friendsfamily": 4,
            "private": 5,
        }
        params = {
            "method": "flickr.photos.search",
            "user_id": user_nsid,
            "per_page": 20,
            "page": page,
            "format": "json",
            "nojsoncallback": 1,
            "extras": "url_q,date_upload,date_taken,description,owner_name,title",
            "privacy_filter": privacy_filter_map.get(privacy, 1)
        }
        resp = oauth.get("https://api.flickr.com/services/rest", params=params)
        if resp.ok:
            data = resp.json().get("photos", {})
            photos = data.get("photo", [])
            pages = data.get("pages", 1)
    else:
        # Get public photos
        params = {
            "method": "flickr.photos.getRecent",
            "per_page": 20,
            "page": page,
            "format": "json",
            "nojsoncallback": 1,
            "extras": "url_q,date_upload,date_taken,description,owner_name,title"
        }
        resp = requests.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
        if resp.ok:
            data = resp.json().get("photos", {})
            photos = data.get("photo", [])
            pages = data.get("pages", 1)
    return templates.TemplateResponse("index.html", {"request": request, "logged_in": logged_in, "photos": photos, "pages": pages, "page": page, "privacy": privacy})

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
        resp = requests.get("https://api.flickr.com/services/rest", params={**params, "api_key": FLICKR_API_KEY})
    if not resp.ok:
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
