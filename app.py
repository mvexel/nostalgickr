from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import secrets
from urllib.parse import urlencode

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

FLICKR_API_KEY = "YOUR_FLICKR_API_KEY"
FLICKR_API_SECRET = "YOUR_FLICKR_SECRET"
FLICKR_OAUTH_CALLBACK = "http://localhost:8000/auth/callback"

# In-memory storage for OAuth tokens (use proper DB in production)
oauth_tokens = {}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user_id = request.cookies.get("flickr_user_id")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "logged_in": user_id is not None
    })

@app.get("/login")
async def login():
    # Generate a random state token
    state = secrets.token_urlsafe(16)
    oauth_tokens[state] = None
    
    # Build Flickr OAuth URL
    params = {
        "api_key": FLICKR_API_KEY,
        "perms": "read",
        "oauth_callback": FLICKR_OAUTH_CALLBACK,
        "state": state
    }
    auth_url = f"https://www.flickr.com/services/oauth/authorize?{urlencode(params)}"
    
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    state = request.query_params.get("state")
    oauth_token = request.query_params.get("oauth_token")
    oauth_verifier = request.query_params.get("oauth_verifier")
    
    if not state or not oauth_token or not oauth_verifier:
        return RedirectResponse("/")
    
    # Exchange the verifier for access token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.flickr.com/services/oauth/access_token",
            data={
                "oauth_consumer_key": FLICKR_API_KEY,
                "oauth_token": oauth_token,
                "oauth_verifier": oauth_verifier,
                "oauth_signature_method": "HMAC-SHA1",
                # You'll need to implement proper signing here
            }
        )
    
    # Parse response to get user info
    # This is simplified - actual implementation needs proper parsing
    user_id = "123456789@N00"  # Would come from actual response
    
    response = RedirectResponse("/")
    response.set_cookie(key="flickr_user_id", value=user_id)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("flickr_user_id")
    return response

@app.get("/api/public_photos")
async def get_public_photos():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.flickr.com/services/rest/",
            params={
                "method": "flickr.photos.getRecent",
                "api_key": FLICKR_API_KEY,
                "format": "json",
                "nojsoncallback": 1,
                "per_page": 20,
                "extras": "url_q"  # Ensure we get the thumbnail URL
            }
        )
        data = response.json()
        # Ensure we have valid photo data
        if 'photos' in data and 'photo' in data['photos']:
            return data
        return {"photos": {"photo": []}}  # Return empty array if no photos

@app.get("/api/user_photos")
async def get_user_photos(request: Request):
    user_id = request.cookies.get("flickr_user_id")
    if not user_id:
        return {"photos": {"photo": []}}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.flickr.com/services/rest/",
            params={
                "method": "flickr.people.getPublicPhotos",
                "api_key": FLICKR_API_KEY,
                "user_id": user_id,
                "format": "json",
                "nojsoncallback": 1,
                "per_page": 20
            }
        )
        return response.json()
