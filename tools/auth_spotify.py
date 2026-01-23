import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

scope = "playlist-read-private user-read-email"

auth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    open_browser=True,
    cache_path=".secrets/spotify_cache",
)

print("Opening browser for Spotify auth...")
token = auth.get_access_token(as_dict=False)
print("✅ Token cached to .secrets/spotify_cache")

