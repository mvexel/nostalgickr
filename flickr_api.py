from typing import Optional, Dict, Any
from requests_oauthlib import OAuth1Session

# Utility functions for interacting with the Flickr API


class FlickrAPI:
    """
    Wrapper for interacting with the Flickr REST API using OAuth authentication.
    Provides methods for fetching user info, contacts, photos, and photo details.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.flickr.com/services/rest"

    def get_oauth_session(
        self, oauth_token: str, oauth_token_secret: str, verifier: Optional[str] = None
    ):
        """
        Create an OAuth1Session for authenticated requests to the Flickr API.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            verifier (Optional[str]): OAuth verifier (optional, for token exchange).

        Returns:
            OAuth1Session: Authenticated session for Flickr API requests.
        """
        return OAuth1Session(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
            verifier=verifier,
        )

    async def fetch_user_info(
        self, oauth_token: str, oauth_token_secret: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch information about the currently authenticated user.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.

        Returns:
            Optional[Dict[str, Any]]: User info dictionary if successful, else None.
        """
        try:
            oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
            params = {
                "method": "flickr.test.login",
                "format": "json",
                "nojsoncallback": 1,
            }
            resp = oauth.get(self.base_url, params=params)
            if resp.ok:
                return resp.json().get("user", {})
            return None
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch user info: {str(e)}")
            return None

    async def fetch_contacts(
        self, oauth_token: str, oauth_token_secret: str
    ) -> Optional[list]:
        """
        Fetch the contact list (friends/family) for the authenticated user.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.

        Returns:
            Optional[list]: List of contact dictionaries if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.contacts.getList",
            "format": "json",
            "nojsoncallback": 1,
            "api_key": self.api_key,
        }
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            data = resp.json().get("contacts", {})
            return data.get("contact", [])
        return None

    async def fetch_photos_of_user(
        self, oauth_token: str, oauth_token_secret: str, nsid: str, per_page: int = 1
    ) -> Optional[list]:
        """
        Fetch photos of another user by NSID (not the logged-in user's own stream).

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            nsid (str): The Flickr NSID of the user whose photos to fetch.
            per_page (int): Number of photos to fetch (default: 1).

        Returns:
            Optional[list]: List of photo dictionaries if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.people.getPhotos",
            "user_id": nsid,
            "per_page": per_page,
            "extras": "url_q,url_m,description,date_upload,date_taken,owner_name,ispublic,isfriend,isfamily",
            "format": "json",
            "nojsoncallback": 1,
            "api_key": self.api_key,
        }
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            return resp.json().get("photos", {}).get("photo", [])
        return None

    async def fetch_own_photos(
        self,
        oauth_token: str,
        oauth_token_secret: str,
        per_page: int = 20,
        privacy_filter: int = None,
    ) -> Optional[list]:
        """
        Fetch the logged-in user's own photos, supporting all privacy levels via flickr.photos.search.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            per_page (int): Number of photos to fetch (default: 20).
            privacy_filter (Optional[int]): Flickr privacy filter (1=public, 2=friends, 3=family, 4=friends+family, 5=private).

        Returns:
            Optional[list]: List of photo dictionaries if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.photos.search",
            "user_id": "me",
            "per_page": per_page,
            "extras": "url_q,url_m,description,date_upload,date_taken,owner_name,ispublic,isfriend,isfamily",
            "format": "json",
            "nojsoncallback": 1,
            "api_key": self.api_key,
        }
        if privacy_filter is not None:
            params["privacy_filter"] = privacy_filter
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            return resp.json().get("photos", {}).get("photo", [])
        return None

    async def fetch_photo_details(
        self, oauth_token: str, oauth_token_secret: str, photo_id: str
    ) -> Optional[dict]:
        """
        Fetch detailed information about a specific photo.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            photo_id (str): The Flickr photo ID to fetch details for.

        Returns:
            Optional[dict]: Photo detail dictionary if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.photos.getInfo",
            "photo_id": photo_id,
            "format": "json",
            "nojsoncallback": 1,
        }
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            return resp.json().get("photo", {})
        return None
