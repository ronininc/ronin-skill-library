# Map Explorer

Explore any area like Google Maps — search what's around, see it on a map, tap in for details. Combines place discovery, map visualization, and rich place details into one flow.

## When to use
User wants to explore an area: "what's around here", "show me restaurants in Scottsdale", "explore downtown Phoenix", "what's near this address". Any request that would be easier on a map than in a list.

## The flow

### 1. Discover
Use `browser.search` to find places in the area. Put the full intent in the query:
- "best taco shops in Mesa Arizona"
- "coffee shops near downtown Phoenix"
- Include the area name, not "near me" (unless location arrived with the message)

### 2. Visualize
Build a map with `widget.create_map_widget`:
- Use `rich_place` elements for results with place IDs (photo + card)
- Use `marker` elements for coordinates without place IDs
- Set `initial_zoom` to fit the area (12-14 for neighborhoods, 10-11 for cities)
- Set `motivation` to the user's need ("taco shops in Mesa")

### 3. Deep dive
When the user taps a place or asks for details:
- Run `places details <place_id>` for hours, ratings, photos, reviews
- Use `map.geocode` to resolve addresses to coordinates
- Use `map.reverse_geocode` to identify what's at coordinates

## Tools in this skill
- `browser.search` — place discovery
- `widget.create_map_widget` — map visualization with pins
- `places details` (CLI) — rich place info by numeric ID
- `map.geocode` — address/name to coordinates
- `map.reverse_geocode` — coordinates to place/address
- `geocode` (CLI) — alternate geocoding

## Rules
- Never invent place IDs or coordinates
- Ground every pin in a real search result
- If search comes back empty, refine the query before giving up
- One area per search — separate calls for multiple neighborhoods
