import os
import re
import requests
import jellyfish
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv

@dataclass
class MatchResult:
    """Data class to store matching results"""
    source_url: str
    source_platform: str
    source_id: str
    target_platform: str
    target_id: Optional[str] = None
    target_url: Optional[str] = None
    method_used: Optional[str] = None
    match_score: Optional[float] = None
    error: Optional[str] = None
    success: bool = False

class MusicPlatform:
    """Base class for music platform handlers"""
    def __init__(self, token: str):
        self.token = token
        
    def get_track_metadata(self, track_id: str) -> Dict:
        """Get track metadata - to be implemented by subclasses"""
        raise NotImplementedError
        
    def search_by_isrc(self, isrc: str) -> Dict:
        """Search by ISRC - to be implemented by subclasses"""
        raise NotImplementedError
        
    def search_by_metadata(self, title: str, artist: str) -> Dict:
        """Search by metadata - to be implemented by subclasses"""
        raise NotImplementedError

class SpotifyPlatform(MusicPlatform):
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        
    @property
    def token(self) -> str:
        if not self._token:
            self._refresh_token()
        return self._token
        
    def _refresh_token(self):
        """Get new Spotify access token"""
        try:
            response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret)
            )
            response.raise_for_status()
            self._token = response.json()["access_token"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get Spotify token: {e}")

    def get_track_metadata(self, track_id: str) -> Dict:
        """Get track metadata from Spotify"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(
                f"https://api.spotify.com/v1/tracks/{track_id}",
                headers=headers
            )
            if response.status_code == 401:  # Token expired
                self._refresh_token()
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(
                    f"https://api.spotify.com/v1/tracks/{track_id}",
                    headers=headers
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Spotify metadata: {e}")

    def search_by_isrc(self, isrc: str) -> Dict:
        """Search Spotify by ISRC"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={
                    "q": f"isrc:{isrc}",
                    "type": "track",
                    "limit": 1
                }
            )
            if response.status_code == 401:  # Token expired
                self._refresh_token()
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={
                        "q": f"isrc:{isrc}",
                        "type": "track",
                        "limit": 1
                    }
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search Spotify by ISRC: {e}")

    def search_by_metadata(self, title: str, artist: str) -> Dict:
        """Search Spotify by title and artist"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            query = f"track:{title} artist:{artist}"
            response = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={
                    "q": query,
                    "type": "track",
                    "limit": 5
                }
            )
            if response.status_code == 401:  # Token expired
                self._refresh_token()
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={
                        "q": query,
                        "type": "track",
                        "limit": 5
                    }
                )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search Spotify by metadata: {e}")

class AppleMusicPlatform(MusicPlatform):
    def get_track_metadata(self, track_id: str) -> Dict:
        """Get track metadata from Apple Music"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(
                f"https://api.music.apple.com/v1/catalog/us/songs/{track_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Apple Music metadata: {e}")
            
    def search_by_isrc(self, isrc: str) -> Dict:
        """Search Apple Music by ISRC"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(
                "https://api.music.apple.com/v1/catalog/us/songs",
                headers=headers,
                params={"filter[isrc]": isrc}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search Apple Music by ISRC: {e}")
            
    def search_by_metadata(self, title: str, artist: str) -> Dict:
        """Search Apple Music by title and artist"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(
                "https://api.music.apple.com/v1/catalog/us/search",
                headers=headers,
                params={
                    "term": f"{title} {artist}",
                    "types": "songs",
                    "limit": 5
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search Apple Music by metadata: {e}")

class MusicServiceMatcher:
    """Enhanced music service matcher that works with URLs"""
    
    SPOTIFY_URL_PATTERN = r"^https?://(?:open\.)?spotify\.com/track/([a-zA-Z0-9]+)"
    APPLE_MUSIC_URL_PATTERNS = [
        r"^https?://music\.apple\.com/\w+/album/[^/]+/\d+\?i=(\d+)",          # Album URL with song ID
        r"^https?://music\.apple\.com/\w+/album/[^/]+/(\d+)(?:\?i=\d+)?",     # Album with optional song ID
        r"^https?://music\.apple\.com/\w+/song/[^/]+/(\d+)",                   # Direct song URL
        r"^https?://music\.apple\.com/\w+/music-video/[^/]+/(\d+)",           # Music video URL
    ]
    
    def __init__(self):
        load_dotenv()
        
        # Initialize platform handlers
        self.spotify = SpotifyPlatform(
            os.getenv('SPOTIFY_CLIENT_ID'),
            os.getenv('SPOTIFY_CLIENT_SECRET')
        )
        self.apple_music = AppleMusicPlatform(
            os.getenv('APPLE_MUSIC_TOKEN')
        )
        
        # Simple cache
        self.cache = {}
        
    def parse_music_url(self, url: str) -> Tuple[str, str]:
        """Parse a music service URL to extract platform and track ID"""
        # Check Spotify URL pattern
        spotify_match = re.match(self.SPOTIFY_URL_PATTERN, url)
        if spotify_match:
            return "spotify", spotify_match.group(1)
            
        # Check Apple Music URL patterns
        for pattern in self.APPLE_MUSIC_URL_PATTERNS:
            apple_match = re.match(pattern, url)
            if apple_match:
                return "apple_music", apple_match.group(1)
            
        raise ValueError(f"Invalid or unsupported music URL: {url}")

    def create_target_url(self, platform: str, track_id: str) -> str:
        """Create the target platform URL from track ID"""
        if platform == "spotify":
            return f"https://open.spotify.com/track/{track_id}"
        elif platform == "apple_music":
            return f"https://music.apple.com/us/song/{track_id}"
        raise ValueError(f"Unsupported platform: {platform}")

    def _find_best_match(self, search_results: Dict, source_title: str, source_artist: str, target_platform: str) -> Optional[Dict]:
        """Find the best matching track from search results using similarity scoring"""
        best_match = None
        best_score = 0
        
        # Get the appropriate results list based on platform
        results_data = (
            search_results.get("results", {}).get("songs", {}).get("data", [])
            if target_platform == "apple_music"
            else search_results.get("tracks", {}).get("items", [])
        )
        
        for track in results_data:
            # Extract track details based on platform
            if target_platform == "apple_music":
                track_title = track.get("attributes", {}).get("name", "")
                track_artist = track.get("attributes", {}).get("artistName", "")
            else:
                track_title = track.get("name", "")
                track_artist = track.get("artists", [{}])[0].get("name", "")
            
            # Skip if missing crucial data
            if not track_title or not track_artist:
                continue
                
            # Calculate similarity scores
            title_score = jellyfish.jaro_winkler(source_title.lower(), track_title.lower())
            artist_score = jellyfish.jaro_winkler(source_artist.lower(), track_artist.lower())
            total_score = (title_score + artist_score) / 2
            
            if total_score > best_score:
                best_score = total_score
                best_match = {
                    "id": track.get("id"),
                    "score": total_score,
                    "title": track_title,
                    "artist": track_artist
                }
        
        # Return best match only if it meets confidence threshold
        return best_match if best_match and best_match["score"] > 0.8 else None

    def match_track(self, url: str) -> MatchResult:
        """Match a track between music services using URL"""
        try:
            # Parse source URL
            source_platform, source_id = self.parse_music_url(url)
            
            # Determine target platform
            target_platform = "apple_music" if source_platform == "spotify" else "spotify"
            
            # Get the appropriate handler for target platform
            target_handler = getattr(self, target_platform)
            
            # Initialize result
            result = MatchResult(
                source_url=url,
                source_platform=source_platform,
                source_id=source_id,
                target_platform=target_platform
            )

            # Check cache
            cache_key = f"{source_platform}:{source_id}"
            if cache_key in self.cache:
                cached_id = self.cache[cache_key]
                if cached_id:
                    result.target_id = cached_id
                    result.target_url = self.create_target_url(target_platform, cached_id)
                    result.method_used = "cache"
                    result.success = True
                    return result

            # Get source metadata using appropriate handler
            source_handler = getattr(self, source_platform)
            try:
                metadata = source_handler.get_track_metadata(source_id)
                
                # Extract common metadata based on platform
                if source_platform == "spotify":
                    title = metadata.get("name", "")
                    artist = metadata.get("artists", [{}])[0].get("name", "")
                    isrc = metadata.get("external_ids", {}).get("isrc")
                else:  # Apple Music
                    if not metadata.get('data'):
                        result.error = "No track data found in Apple Music response"
                        return result
                    track = metadata['data'][0]['attributes']
                    title = track.get("name", "")
                    artist = track.get("artistName", "")
                    isrc = track.get("isrc")

                print(f"\nExtracting metadata for: {title} by {artist}")
                print(f"ISRC: {isrc if isrc else 'Not available'}")

                # Try ISRC-based match first if available
                if isrc:
                    try:
                        print("\nAttempting ISRC-based match...")
                        search_results = target_handler.search_by_isrc(isrc)
                        
                        if search_results:
                            if target_platform == "spotify" and search_results.get("tracks", {}).get("items"):
                                track = search_results["tracks"]["items"][0]
                                result.target_id = track["id"]
                                print(f"Found Spotify match: {track['name']} by {track['artists'][0]['name']}")
                            elif target_platform == "apple_music" and search_results.get("data"):
                                track = search_results["data"][0]
                                result.target_id = track["id"]
                                print(f"Found Apple Music match: {track['attributes']['name']} by {track['attributes']['artistName']}")
                            
                            if result.target_id:
                                result.target_url = self.create_target_url(target_platform, result.target_id)
                                result.method_used = "isrc_match"
                                result.success = True
                                self.cache[cache_key] = result.target_id
                                return result
                                
                    except Exception as e:
                        print(f"ISRC search failed: {str(e)}")
                        print("Falling back to metadata search...")

                # Fallback to metadata-based search
                if title and artist:  # Only proceed if we have both title and artist
                    try:
                        print(f"\nAttempting metadata-based search for: {title} by {artist}")
                        search_results = target_handler.search_by_metadata(title, artist)
                        best_match = self._find_best_match(search_results, title, artist, target_platform)
                        
                        if best_match:
                            result.target_id = best_match["id"]
                            result.target_url = self.create_target_url(target_platform, best_match["id"])
                            result.method_used = "metadata_match"
                            result.match_score = best_match["score"]
                            result.success = True
                            self.cache[cache_key] = result.target_id
                            print(f"Found match with confidence score: {best_match['score']:.2f}")
                            print(f"Matched: {best_match['title']} by {best_match['artist']}")
                            return result
                        else:
                            print("No suitable metadata match found")
                            
                    except Exception as e:
                        print(f"Metadata search failed: {str(e)}")
                        result.error = f"Metadata search failed: {str(e)}"
                        return result

                result.error = "No suitable match found"
                self.cache[cache_key] = None
                return result
                
            except Exception as e:
                print(f"\nError getting source metadata: {str(e)}")
                result.error = f"Failed to get source metadata: {str(e)}"
                return result
            
        except Exception as e:
            return MatchResult(
                source_url=url,
                source_platform=source_platform if 'source_platform' in locals() else None,
                source_id=source_id if 'source_id' in locals() else None,
                target_platform=target_platform if 'target_platform' in locals() else None,
                error=str(e),
                success=False
            )

def main():
    """Main function to run the music service matcher"""
    matcher = MusicServiceMatcher()
    
    print("\nWelcome to the Music Service Matcher!")
    print("This tool converts between Spotify and Apple Music track URLs")
    print("\nExample formats:")
    print("  Spotify: https://open.spotify.com/track/2ltvvftNngVjO6xhqVQd9M")
    print("  Apple Music: https://music.apple.com/us/song/1780828941")
    
    while True:
        print("\n" + "-"*50)
        url = input("\nEnter a music URL (or 'quit' to exit): ").strip()
        
        if url.lower() == 'quit':
            print("\nThank you for using Music Service Matcher!")
            break
            
        try:
            print("\nProcessing request...")
            result = matcher.match_track(url)
            
            if result.success:
                print("\n✅ Match found!")
                print(f"Source: {result.source_platform} ({result.source_id})")
                print(f"Target: {result.target_platform} ({result.target_id})")
                print(f"Method used: {result.method_used}")
                if result.match_score:
                    print(f"Match confidence score: {result.match_score:.2f}")
                print(f"\nTarget URL: {result.target_url}")
            else:
                print("\n❌ No match found")
                if result.error:
                    print(f"Error: {result.error}")
                
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            print("Please try again with a different URL")

if __name__ == "__main__":
    main()