# V7 — Dark matchday design

## Update your existing Windows project

1. Stop Flask with Ctrl+C. Back up your project folder.
2. Extract this ZIP and copy its contents into your existing project folder, replacing code files. **Keep your existing `.env`, `.venv` and `instance` folder.** The ZIP does not contain those folders or your database.
3. In the existing project terminal, run:

```powershell
.\.venv\Scripts\python.exe app.py
```

4. Open http://127.0.0.1:5000 and press **Ctrl+F5** once to refresh the stylesheet and script.

No import, API key changes, database reset or model retraining are required for this visual update.

## What's included

- Dark charcoal theme with lime, violet and cyan accents; responsive tables and navigation.
- Supplied Premier League logo, trophy hero and Haaland/Bruno derby image.
- Club crests across standings, club pages, fixtures, comparisons and forecasts.
- Headshots and quick selections for Haaland, Mbeumo, Bruno Fernandes, Harry Maguire and Declan Rice on Player Value. Other matched players use their official portrait where available.
- Player leader cards, relative contribution bars and name/club search. All rankings remain based on imported records with coverage labels.
- Club comparison crests, form, points charts, comparison bars and a Swap clubs button.
- Pep Guardiola's thinking photo on What if, club crests beside score inputs and a count of completed score pairs. Calculate table still submits to the existing server-side calculation.
- Predicted/recorded valuation bars, readable metric explanations and a dark scatter plot. Detailed methodology remains expandable.
- Visible keyboard focus, reduced-motion support, mobile layouts and image-failure fallbacks.

No prediction, valuation, import or training logic was changed. Dark plot colours affect rendering only. Player pictures do not imply the current kit matches the historical valuation season.

See ASSET_CREDITS.md for image sources.
