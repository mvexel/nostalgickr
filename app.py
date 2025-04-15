from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

FLICKR_API_KEY = "YOUR_FLICKR_API_KEY"  # You'll need to get this from Flickr

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
                "per_page": 20
            }
        )
        return response.json()

@app.get("/api/user_photos")
async def get_user_photos(user_id: str):
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
