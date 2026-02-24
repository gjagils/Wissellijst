#!/usr/bin/env python3
"""
Spotify authentication script.
Run this once to authenticate with Spotify and save the token.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.spotify_client import get_auth_url, handle_callback


def authenticate():
    """Authenticate with Spotify."""

    print("\n🎵 Spotify Authenticatie")
    print("=" * 60)

    # Get auth URL
    auth_url = get_auth_url()

    print("\n📋 Stap 1: Open deze URL in je browser:\n")
    print(f"   {auth_url}\n")

    print("📋 Stap 2: Log in met Spotify en geef toestemming\n")

    print("📋 Stap 3: Je wordt doorgestuurd naar een URL zoals:")
    print("   http://localhost:8888/callback?code=AQA...\n")

    print("📋 Stap 4: Kopieer de HELE callback URL en plak hieronder:\n")

    # Get callback URL from user
    callback_url = input("Plak de callback URL hier: ").strip()

    # Extract code from URL
    if "?code=" not in callback_url:
        print("\n❌ Ongeldige URL! De URL moet '?code=' bevatten.")
        print("   Bijvoorbeeld: http://localhost:8888/callback?code=AQA...")
        sys.exit(1)

    # Extract the code parameter
    code = callback_url.split("?code=")[1].split("&")[0]

    print(f"\n🔑 Code extracted: {code[:20]}...")
    print("⏳ Authenticeren met Spotify...")

    # Handle callback
    try:
        handle_callback(code)
        print("\n✅ Succesvol geauthenticeerd met Spotify!")
        print("🎉 Token opgeslagen in /app/.secrets/spotify_cache")
        print("\nJe kunt nu de API gebruiken!")

    except Exception as e:
        print(f"\n❌ Authenticatie mislukt: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        authenticate()
    except KeyboardInterrupt:
        print("\n\n❌ Geannuleerd door gebruiker")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fout: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
