import os
import requests
import jellyfish
from typing import Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class MatchResult:
    """Data class to store matching results"""
    source_id: str
    source_platform: str
    target_platform: str
    target_id: Optional[str] = None
    target_url: Optional[str] = None
    method_used: Optional[str] = None
    match_score: Optional[float] = None
    error: Optional[str] = None
    success: bool = False

class PlatformMatcher:
    def __init__(self):
        load_dotenv()
        self._spotify_token = None
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.apple_token = os.getenv('APPLE_MUSIC_TOKEN')
        self.cache = {}

    def _get_spotify_token(self) -> str:
        """Get or refresh Spotify access token"""
        if not self._spotify_token:
            try:
                response = requests.post(
                    "https://accounts.spotify.com/api/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self.spotify_client_id, self.spotify_client_secret)
                )
                response.raise_for_status()
                self._spotify_token = response.json()["access_token"]
            except requests.exceptions.RequestException as e:
                raise Exception(f"Failed to get Spotify token: {e}")
        return self._spotify_token

    def _get_track_metadata(self, track_id: str, platform: str) -> Dict:
        """Get track metadata from specified platform"""
        try:
            if platform == "spotify":
                headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                response = requests.get(
                    f"https://api.spotify.com/v1/tracks/{track_id}",
                    headers=headers
                )
                if response.status_code == 401:  # Token expired
                    self._spotify_token = None  # Reset token
                    headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                    response = requests.get(
                        f"https://api.spotify.com/v1/tracks/{track_id}",
                        headers=headers
                    )
            else:  # apple_music
                headers = {"Authorization": f"Bearer {self.apple_token}"}
                response = requests.get(
                    f"https://api.music.apple.com/v1/catalog/us/songs/{track_id}",
                    headers=headers
                )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch {platform} metadata: {e}")

    def _search_by_isrc(self, isrc: str, platform: str) -> Dict:
        """Search for track by ISRC"""
        try:
            if platform == "spotify":
                headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                response = requests.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={"q": f"isrc:{isrc}", "type": "track", "limit": 1}
                )
                if response.status_code == 401:  # Token expired
                    self._spotify_token = None  # Reset token
                    headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                    response = requests.get(
                        "https://api.spotify.com/v1/search",
                        headers=headers,
                        params={"q": f"isrc:{isrc}", "type": "track", "limit": 1}
                    )
            else:  # apple_music
                headers = {"Authorization": f"Bearer {self.apple_token}"}
                response = requests.get(
                    "https://api.music.apple.com/v1/catalog/us/songs",
                    headers=headers,
                    params={"filter[isrc]": isrc}
                )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search {platform} by ISRC: {e}")

    def _search_by_metadata(self, title: str, artist: str, platform: str) -> Dict:
        """Search for track by title and artist"""
        try:
            if platform == "spotify":
                headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                query = f"track:{title} artist:{artist}"
                response = requests.get(
                    "https://api.spotify.com/v1/search",
                    headers=headers,
                    params={"q": query, "type": "track", "limit": 5}
                )
                if response.status_code == 401:  # Token expired
                    self._spotify_token = None  # Reset token
                    headers = {"Authorization": f"Bearer {self._get_spotify_token()}"}
                    response = requests.get(
                        "https://api.spotify.com/v1/search",
                        headers=headers,
                        params={"q": query, "type": "track", "limit": 5}
                    )
            else:  # apple_music
                headers = {"Authorization": f"Bearer {self.apple_token}"}
                response = requests.get(
                    "https://api.music.apple.com/v1/catalog/us/search",
                    headers=headers,
                    params={"term": f"{title} {artist}", "types": "songs", "limit": 5}
                )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search {platform} by metadata: {e}")

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using normalized Levenshtein distance"""
        try:
            # Convert strings to lowercase for comparison
            s1, s2 = str1.lower(), str2.lower()
            
            # Get Levenshtein distance
            distance = jellyfish.levenshtein_distance(s1, s2)
            
            # Normalize to get similarity score between 0 and 1
            # Using max length of strings as normalization factor
            max_len = max(len(s1), len(s2))
            if max_len == 0:
                return 0.0
                
            # Convert distance to similarity (1 - normalized_distance)
            similarity = 1 - (distance / max_len)
            
            print(f"Comparing: '{s1}' with '{s2}' -> similarity: {similarity:.2f}")
            return similarity
            
        except Exception as e:
            print(f"Warning: Error calculating similarity: {str(e)}")
            print(f"String 1: {str1}")
            print(f"String 2: {str2}")
            return 0.0

    def match_track_id(self, track_id: str, source_platform: str) -> MatchResult:
        """Match a track between platforms using track ID"""
        target_platform = "apple_music" if source_platform == "spotify" else "spotify"
        
        result = MatchResult(
            source_id=track_id,
            source_platform=source_platform,
            target_platform=target_platform
        )

        try:
            # Check cache
            cache_key = f"{source_platform}:{track_id}"
            if cache_key in self.cache:
                cached_id = self.cache[cache_key]
                if cached_id:
                    result.target_id = cached_id
                    result.method_used = "cache"
                    result.success = True
                    return result

            # Get source metadata
            metadata = self._get_track_metadata(track_id, source_platform)
            
            # Extract metadata based on platform
            if source_platform == "spotify":
                title = metadata.get("name", "")
                artist = metadata.get("artists", [{}])[0].get("name", "")
                isrc = metadata.get("external_ids", {}).get("isrc")
            else:  # apple_music
                if not metadata.get('data'):
                    result.error = "No track data found"
                    return result
                track = metadata['data'][0]['attributes']
                title = track.get("name", "")
                artist = track.get("artistName", "")
                isrc = track.get("isrc")

            print(f"\nFound source track: '{title}' by {artist}")
            print(f"ISRC: {isrc or 'Not available'}")

            # Try ISRC match first
            if isrc:
                print("Attempting ISRC match...")
                search_results = self._search_by_isrc(isrc, target_platform)
                
                if target_platform == "spotify" and search_results.get("tracks", {}).get("items"):
                    result.target_id = search_results["tracks"]["items"][0]["id"]
                    result.method_used = "isrc_match"
                    result.success = True
                    self.cache[cache_key] = result.target_id
                    return result
                elif target_platform == "apple_music" and search_results.get("data"):
                    result.target_id = search_results["data"][0]["id"]
                    result.method_used = "isrc_match"
                    result.success = True
                    self.cache[cache_key] = result.target_id
                    return result

            # Fallback to metadata search
            if title and artist:
                print("ISRC match failed or not available, trying metadata match...")
                search_results = self._search_by_metadata(title, artist, target_platform)
                
                results_data = (
                    search_results.get("results", {}).get("songs", {}).get("data", [])
                    if target_platform == "apple_music"
                    else search_results.get("tracks", {}).get("items", [])
                )

                best_match = None
                best_score = 0

                for track in results_data:
                    if target_platform == "apple_music":
                        track_title = track.get("attributes", {}).get("name", "")
                        track_artist = track.get("attributes", {}).get("artistName", "")
                    else:
                        track_title = track.get("name", "")
                        track_artist = track.get("artists", [{}])[0].get("name", "")

                    if not track_title or not track_artist:
                        continue

                    title_score = self._calculate_similarity(title, track_title)
                    artist_score = self._calculate_similarity(artist, track_artist)
                    total_score = (title_score + artist_score) / 2

                    if total_score > best_score:
                        best_score = total_score
                        best_match = {"id": track.get("id"), "score": total_score}

                if best_match and best_match["score"] > 0.8:
                    result.target_id = best_match["id"]
                    result.method_used = "metadata_match"
                    result.match_score = best_match["score"]
                    result.success = True
                    self.cache[cache_key] = result.target_id
                    return result

            result.error = "No suitable match found"
            self.cache[cache_key] = None
            return result

        except Exception as e:
            result.error = str(e)
            return result

def validate_result(result: MatchResult) -> bool:
    """Validate the match result by checking if the target ID exists"""
    try:
        matcher = PlatformMatcher()
        metadata = matcher._get_track_metadata(result.target_id, result.target_platform)
        return bool(metadata.get('data') if result.target_platform == 'apple_music' else metadata.get('id'))
    except:
        return False

def main():
    matcher = PlatformMatcher()
    
    print("\nPlatform ID Music Matcher")
    print("------------------------")
    
    while True:
        platform = input("\nEnter source platform (spotify/apple/quit): ").strip().lower()
        
        if platform == 'quit':
            print("\nGoodbye!")
            break
            
        if platform not in ['spotify', 'apple']:
            print("Invalid platform. Please enter 'spotify' or 'apple'")
            continue
            
        track_id = input("Enter track ID: ").strip()
        
        # Convert 'apple' to 'apple_music' for internal use
        source_platform = 'apple_music' if platform == 'apple' else platform
        
        try:
            print("\nSearching for match...")
            result = matcher.match_track_id(track_id, source_platform)
            
            if result.success:
                print("\n✅ Match found!")
                print(f"Source platform: {result.source_platform}")
                print(f"Source ID: {result.source_id}")
                print(f"Target platform: {result.target_platform}")
                print(f"Target ID: {result.target_id}")
                print(f"Method used: {result.method_used}")
                if result.match_score:
                    print(f"Match confidence: {result.match_score:.2f}")
                    
                # Validate the result
                if validate_result(result):
                    print("✅ Match validated successfully")
                else:
                    print("⚠️ Warning: Match validation failed")
            else:
                print("\n❌ No match found")
                if result.error:
                    print(f"Error: {result.error}")
                    
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    main()