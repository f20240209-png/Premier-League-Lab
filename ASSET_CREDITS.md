# Image sources

This independent student project is not affiliated with the Premier League, clubs or pictured people. The images do not imply endorsement. Imagery is separate from the historical statistics and model inputs; portrait kits may belong to a different season.

- **Premier League logo, trophy photograph and Manchester derby photograph:** supplied by the project owner for this redesign. Original photographer / licence details were not supplied.
- **Club crests and player portraits:** Premier League media CDN, `resources.premierleague.com`. Player identifiers and full names were matched from the public official Fantasy Premier League bootstrap response on 24 September 2026. Club crests use stable Premier League team codes; source-specific name aliases are resolved only for presentation.
- **Pep Guardiola thinking on the touchline:** Associated Press photograph, via [Yahoo Sports](https://sports.yahoo.com/article/man-city-faces-mid-winter-121638439.html). Credit is shown beside the photo on desktop.
- Exact downloaded asset URLs are retained in `static/media/sources.json`. The additional player portrait URL lookup is in `static/media/players.json`.

These media assets retain their original owners' rights; they are not covered by the historical dataset's CC0 licence or by any source-code licence. Attribution does not itself grant a reuse licence.

## Behaviour

27 club crests and 13 featured player portraits are bundled for reliable local display. Other explicitly matched player portraits load from the Premier League CDN. Missing or failed images fall back to initials, retaining the player or club name. No image requests use a football API key, and opening a page does not consume your paid API request quota. Portrait lookups never change player records, join model data or infer a historical club from a shirt.
