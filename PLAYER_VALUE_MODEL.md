# Player Market Value — model card

Built and tested on 22 September 2026.

## Task and source

Predict a player's historical Transfermarkt market valuation in EUR from goals,
assists, EPL minutes, age at valuation and position. These are estimates of
market value, not actual transfer fees or investment recommendations.

Source: https://github.com/dcaribou/transfermarkt-datasets (publisher CC0-1.0).
The publisher reports paused updates since July 2026. Our extract's latest
valuation is 2026-06-03; current 2026/27 player values are unavailable.
Source hashes, exact row counts and download URLs: `data/player_values/provenance.json`.

## Dataset construction

- Filter game records to competition GB1; retain seasons with 380 unique games.
- Join appearances by game ID, aggregate by player ID and season, including all
  club spells. Only EPL appearances are counted.
- Reject duplicate identities/appearances. Drop any player-season with missing,
  negative or non-integer goals, assists or minutes; do not impute them as zero.
- Require 450–5,000 minutes, a known date of birth, a recognised position and
  age 16–45 at valuation. This excludes low-minute and incomplete profiles.
- Use the first positive valuation strictly after the season's final EPL game,
  within 75 days and no later than August 1. Future-dated valuations are excluded.
- Age comes from date of birth and that valuation date. Position comes from the
  downloaded profile; historical position changes cannot be verified.
- Use all eligible labelled records, without selecting players by price or
  model fit. This leaves 1,994 examples, not the full set of EPL players.

## Training and evaluation

Ordinary least squares `sklearn.linear_model.LinearRegression`, standardisation
of the four numeric features and one-hot encoding of position with one category
dropped. Features, means and scales are fit using only training rows. Negative
predictions are clipped to zero consistently during evaluation and inference.
No model selection or hyperparameter tuning on the test set was performed.

Training: 2021/22–2024/25, 1595 examples, latest label 2025-06-18.
Holdout: 2025/26, 399 examples, labels 2026-05-26–2026-06-03.
This frozen model is also used for the custom profile form. It is not refit on
holdout labels. 294 test players occurred in earlier training
seasons, so this evaluates later seasons, not exclusively unseen identities.
Names, IDs, current club, latest market value and highest-ever value are not features.

| Measure | Linear Regression | Training-median baseline |
| --- | ---: | ---: |
| MAE (EUR) | 12,074,681 | 17,059,649 |
| RMSE (EUR) | 17,940,087 | 26,047,296 |
| R² | 0.424 | -0.213 |

The median baseline always predicts EUR 18,000,000.
9 holdout predictions required clipping to zero.
MAE is an average error across this cohort, not a confidence interval for an
individual player. R² is not classification accuracy.

## Limits and next improvements

Large errors remain, particularly at high valuations. Goals and assists favour
attacking output; defending and goalkeeping contributions are poorly described.
Contract length, reputation, injuries, non-EPL performance and market conditions
are absent. Position metadata is not fully historical, and published source
coverage can be incomplete. Retrospective source corrections may also differ
from what was available on the original date.

The selected player's difference from the recorded value is a prediction error,
not evidence of undervaluation. Manual profiles have no verified actual-value
comparison and use the same historical model. Out-of-training-range inputs are
flagged. Broader ranges are rejected rather than extrapolated without bounds.

Before upgrading this model, reserve a new future evaluation set or use rolling
validation inside the earlier seasons. Compare a log-target linear model and
regularised regression using training/validation only; add richer features only
when their historical dates are verifiable.

## Reproduction and storage

Run `python manage.py train-values` after installing `requirements.txt`.
This trains without network access from the checksum-verified included CSV.
The UI is `/player-values`. Model coefficients, reports and comparison records
are stored as JSON in a new `fl_value_models` table; no pickle loading is used.
Use `--source-dir PATH` to rebuild from raw CSVs or `--refresh` to download the
publisher's files. Unchanged inputs are idempotent; failure preserves the last
successful model. Match prediction models and imported match data are separate.
