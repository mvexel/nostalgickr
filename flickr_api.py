from typing import Optional, Dict, Any
from requests_oauthlib import OAuth1Session

# Utility functions for interacting with the Flickr API

class FlickrAPI:
    """Wrapper for interacting with the Flickr REST API using OAuth authentication.

    Provides methods for fetching user info, contacts, photos, and photo details.
    All methods require valid OAuth tokens for authenticated requests.

    Attributes:
        api_key (str): Flickr API key
        api_secret (str): Flickr API secret
        base_url (str): Base URL for Flickr API endpoints
    """

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.flickr.com/services/rest"

    async def fetch_user_groups(
        self,
        oauth_token: str,
        oauth_token_secret: str,
        user_id: str,
        extras: str = None
    ) -> Optional[list]:
        """Fetch the groups the authenticated user is a member of.

        Uses flickr.people.getGroups API endpoint.

        Args:
            oauth_token: Valid OAuth token for authentication
            oauth_token_secret: Valid OAuth token secret
            user_id: Flickr NSID of the user to fetch groups for
            extras: Optional comma-delimited extra fields to include.
                Common values: 'privacy,throttle,restrictions'

        Returns:
            List of group dictionaries if successful, None on failure.
            Each group dict contains:
                - nsid: Group ID
                - name: Group name
                - members: Count of members
                - privacy: Group privacy level
                - other fields depending on extras requested

        Raises:
            None: Errors are caught and logged, returns None on failure
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.people.getGroups",
            "format": "json",
            "nojsoncallback": 1,
            "api_key": self.api_key,
            "user_id": user_id,
        }
        if extras:
            params["extras"] = extras
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            data = resp.json().get("groups", {})
            return data.get("group", [])
        return None

    def get_oauth_session(
        self,
        oauth_token: str,
        oauth_token_secret: str,
        verifier: Optional[str] = None
    ) -> OAuth1Session:
        """Create an authenticated OAuth1Session for Flickr API requests.

        Args:
            oauth_token: Valid OAuth token
            oauth_token_secret: Valid OAuth token secret
            verifier: OAuth verifier string (only needed during token exchange)

        Returns:
            Configured OAuth1Session instance ready for API requests

        Raises:
            None: This is a simple wrapper that shouldn't raise exceptions
        """
        return OAuth1Session(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
            verifier=verifier,
        )

    async def fetch_user_info(
        self, 
        oauth_token: str, 
        oauth_token_secret: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch information about the currently authenticated user.

        Uses flickr.test.login API endpoint which returns basic user info.

        Args:
            oauth_token: Valid OAuth token for authentication
            oauth_token_secret: Valid OAuth token secret

        Returns:
            Dictionary containing user info if successful, None on failure.
            Contains keys like:
                - id: User NSID
                - username: Dictionary with _content field for display name
                - other profile fields

        Raises:
            None: Errors are caught and logged, returns None on failure
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
        self, 
        oauth_token: str, 
        oauth_token_secret: str
    ) -> Optional[list]:
        """Fetch the contact list (friends/family) for authenticated user.

        Uses flickr.contacts.getList API endpoint.

        Args:
            oauth_token: Valid OAuth token for authentication
            oauth_token_secret: Valid OAuth token secret

        Returns:
            List of contact dictionaries if successful, None on failure.
            Each contact contains:
                - nsid: Contact's Flickr ID
                - username: Contact's username
                - realname: Contact's real name (if available)
                - friend: Boolean if contact is a friend
                - family: Boolean if contact is family

        Raises:
            None: Errors are caught and logged, returns None on failure
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
        self,
        oauth_token: str,
        oauth_token_secret: str,
        nsid: str,
        per_page: int = 1
    ) -> Optional[list]:
        """Fetch photos of another user by NSID.

        Uses flickr.people.getPhotos API endpoint.

        Args:
            oauth_token: Valid OAuth token for authentication
            oauth_token_secret: Valid OAuth token secret
            nsid: Flickr NSID of the user whose photos to fetch
            per_page: Number of photos to return (default: 1)

        Returns:
            List of photo dictionaries if successful, None on failure.
            Each photo contains:
                - id: Photo ID
                - title: Photo title
                - url_q: Square thumbnail URL
                - url_m: Medium size URL
                - date_upload: Upload timestamp
                - date_taken: Taken date string
                - owner_name: Owner's display name

        Raises:
            None: Errors are caught and logged, returns None on failure
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
        page: int = 1,
        privacy_filter: int = None,
    ) -> Optional[dict]:
        """Fetch the logged-in user's own photos with privacy filtering.

        Uses flickr.photos.search API endpoint with user_id="me".

        Args:
            oauth_token: Valid OAuth token for authentication
            oauth_token_secret: Valid OAuth token secret
            per_page: Number of photos per page (default: 20)
            page: Page number to fetch (default: 1)
            privacy_filter: Optional privacy level (1-5):
                1=public, 2=friends, 3=family, 4=friends+family, 5=private

        Returns:
            Dictionary containing:
                - photos: List of photo dictionaries
                - pages: Total pages available
                - total: Total photos available
            Returns None on failure.

            Photo dictionaries contain:
                - id: Photo ID
                - title: Photo title
                - url_q: Square thumbnail URL
                - url_m: Medium size URL
                - date_upload: Upload timestamp
                - date_taken: Taken date string
                - ispublic: Boolean if public
                - isfriend: Boolean if visible to friends
                - isfamily: Boolean if visible to family

        Raises:
            None: Errors are caught and logged, returns None on failure
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
        params["page"] = page
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            photos_data = resp.json().get("photos", {})
            return {
                "photos": photos_data.get("photo", []),
                "pages": photos_data.get("pages", 1),
                "total": photos_data.get("total", 0)
            }
        return None

    async def fetch_contacts_photos(
        self,
        oauth_token: str,
        oauth_token_secret: str,
        count: int = 50,
        just_friends: bool = False,
        single_photo: bool = True,
        include_self: bool = False,
        extras: str = "date_upload,date_taken,owner_name"
    ) -> Optional[list]:
        """
        Fetch recent photos from contacts using flickr.photos.getContactsPhotos.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            count (int): Number of photos to return (default: 50, max: 50).
            just_friends (bool): Only show photos from friends and family (default: False).
            single_photo (bool): Only fetch one photo per contact (default: True).
            include_self (bool): Include photos from the calling user (default: False).
            extras (str): Comma-delimited extra fields to fetch.

        Returns:
            Optional[list]: List of photo dictionaries if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.photos.getContactsPhotos",
            "count": count,
            "just_friends": int(just_friends),
            "single_photo": int(single_photo),
            "include_self": int(include_self),
            "format": "json",
            "nojsoncallback": 1,
        }
        if extras:
            params["extras"] = extras
            
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            return resp.json().get("photos", {}).get("photo", [])
        return None

    async def fetch_photo_sizes(
        self, oauth_token: str, oauth_token_secret: str, photo_id: str
    ) -> Optional[list]:
        """
        Fetch available sizes for a photo.

        Args:
            oauth_token (str): OAuth token.
            oauth_token_secret (str): OAuth token secret.
            photo_id (str): The Flickr photo ID to fetch sizes for.

        Returns:
            Optional[list]: List of size dictionaries if successful, else None.
        """
        oauth = self.get_oauth_session(oauth_token, oauth_token_secret)
        params = {
            "method": "flickr.photos.getSizes",
            "photo_id": photo_id,
            "format": "json",
            "nojsoncallback": 1,
        }
        resp = oauth.get(self.base_url, params=params)
        if resp.ok:
            return resp.json().get("sizes", {}).get("size", [])
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
