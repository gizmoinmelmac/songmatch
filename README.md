# Music Platform Matcher

This project provides tools for matching songs between Spotify and Apple Music platforms. It offers two different approaches:

1. URL-based matching (`songmatch.py`)
2. ID-based matching (`platform_matcher.py`)

## Requirements

```bash
pip install requests python-dotenv jellyfish
```

## Configuration

Create a `.env` file in the root directory with your API credentials:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
APPLE_MUSIC_TOKEN=your_apple_music_token
```

## URL-Based Matching (`songmatch.py`)

This version accepts full Spotify or Apple Music URLs and converts them to the other platform.

### Supported URL Formats

- Spotify: `https://open.spotify.com/track/[ID]`
- Apple Music:
  - `https://music.apple.com/[country]/album/[name]/[album_id]?i=[song_id]`
  - `https://music.apple.com/[country]/song/[name]/[song_id]`
  - `https://music.apple.com/[country]/music-video/[name]/[song_id]`

### Usage

```python
from songmatch import MusicServiceMatcher

matcher = MusicServiceMatcher()
result = matcher.match_track("https://open.spotify.com/track/2ltvvftNngVjO6xhqVQd9M")

if result.success:
    print(f"Found match: {result.target_url}")
```

## ID-Based Matching (`platform_matcher.py`)

This version works directly with platform IDs, making it more suitable for integration into larger systems where you already have the track IDs.

### Usage

```python
from platform_matcher import PlatformMatcher

matcher = PlatformMatcher()
result = matcher.match_track_id("2ltvvftNngVjO6xhqVQd9M", "spotify")

if result.success:
    print(f"Apple Music ID: {result.target_id}")
```

## Matching Process

Both versions use the same matching strategy:

1. **ISRC Match** (Primary Method):
   - Retrieves the ISRC (International Standard Recording Code) from the source platform
   - Searches for this ISRC on the target platform
   - Most accurate when available

2. **Metadata Match** (Fallback):
   - Uses track title and artist name for matching
   - Employs Levenshtein distance for fuzzy string matching
   - Requires a confidence score above 0.6 (60%) to consider it a match

3. **Caching**:
   - Successful matches are cached to improve performance
   - Cache is maintained in memory during the session

## Error Handling

Both implementations include comprehensive error handling:

- Network errors
- API authentication issues
- Invalid URLs/IDs
- Missing track data
- Failed matches

## CLI Interface

Both scripts include a command-line interface for testing:

```bash
# For URL matching:
python songmatch.py

# For ID matching:
python platform_matcher.py
```

## Response Format

Both matchers return a `MatchResult` object containing:

- `success`: Boolean indicating if a match was found
- `source_id`: Original track ID
- `target_id`: Matched track ID
- `method_used`: How the match was found ("isrc_match", "metadata_match", or "cache")
- `match_score`: Confidence score for metadata matches
- `error`: Error message if matching failed

## Limitations

- Requires valid API credentials for both platforms
- Match quality depends on metadata consistency between platforms
- Some tracks might not be available on both platforms
- Regional restrictions might affect availability

## Contributing

Feel free to submit issues and enhancement requests!
