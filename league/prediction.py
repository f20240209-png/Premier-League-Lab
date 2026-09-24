from collections import defaultdict
from datetime import datetime
import numpy as np
from sqlalchemy import select
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, log_loss, confusion_matrix

from .analytics import feature_rows, history_features, result_for, FEATURES
from .importer import FINISHED, SCHEDULED
from .storage import Match, Season, ModelRun, Forecast, utcnow
from .real_data import real_matches, require_complete_season
from .forest import fit_forest, forest_probabilities

LABELS = ["A", "D", "H"]


def fit(rows):
    x = np.asarray([r["x"] for r in rows], dtype=float)
    y = [r["y"] for r in rows]
    if set(y) != set(LABELS):
        raise ValueError("Training requires home wins, draws and away wins.")
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(C=1.0, max_iter=1000, random_state=42).fit(scaler.transform(x), y)
    return {"features": FEATURES, "classes": list(model.classes_), "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(), "coef": model.coef_.tolist(), "intercept": model.intercept_.tolist()}


def probabilities(parameters, x):
    if parameters.get('algorithm') == 'random_forest':
        return forest_probabilities(parameters, x)
    z = (np.asarray(x) - parameters["mean"]) / parameters["scale"]
    logits = np.asarray(parameters["coef"]) @ z + parameters["intercept"]
    exp = np.exp(logits - logits.max())
    return dict(zip(parameters["classes"], (exp / exp.sum()).tolist()))


def metrics(y, probs):
    p = np.asarray([[row[c] for c in LABELS] for row in probs])
    guesses = [LABELS[i] for i in p.argmax(axis=1)]
    bins = []
    # Calibration of home-win probability, fixed bins rather than tuned to holdout.
    for low in (0, .2, .4, .6, .8):
        indices = [i for i, row in enumerate(probs) if low <= row["H"] < low + .2 + (1e-9 if low == .8 else 0)]
        if indices:
            bins.append({"bucket": f"{int(low*100)}-{int((low+.2)*100)}%", "count": len(indices),
                         "predicted": float(np.mean([probs[i]["H"] for i in indices])),
                         "observed": float(np.mean([y[i] == "H" for i in indices]))})
    return {"accuracy": float(accuracy_score(y, guesses)), "log_loss": float(log_loss(y, p, labels=LABELS)),
            "confusion": confusion_matrix(y, guesses, labels=LABELS).tolist(), "calibration": bins}


def compare_candidates(training, test):
    # Whole UTC dates stay together. Selection only sees the earlier-season tail.
    dates = sorted({r['match'].kickoff.date() for r in training})
    split = dates[int(len(dates)*0.75)]
    fit_rows = [r for r in training if r['match'].kickoff.date() < split]
    validation = [r for r in training if r['match'].kickoff.date() >= split]
    if len(fit_rows) < 50 or len(validation) < 20:
        raise ValueError('Comparison requires 50 earlier fitting and 20 later validation fixtures.')
    fitters = {'logistic_regression':fit, 'random_forest':fit_forest}
    validation_scores = {}
    for name, fitter in fitters.items():
        parameters = fitter(fit_rows)
        validation_scores[name] = metrics([r['y'] for r in validation],
            [probabilities(parameters,r['x']) for r in validation])
    selected = min(fitters, key=lambda name:validation_scores[name]['log_loss'])
    results = {}
    selected_parameters = None
    selected_predictions = None
    for name, fitter in fitters.items():
        parameters = fitter(training)
        predicted = [probabilities(parameters,r['x']) for r in test]
        results[name] = dict(validation=validation_scores[name],test=metrics([r['y'] for r in test],predicted))
        if name == selected:
            selected_parameters,selected_predictions = parameters,predicted
    return selected_parameters,selected_predictions,dict(selected=selected,candidates=results,
        fit_count=len(fit_rows),validation_count=len(validation),validation_start=str(split),
        validation_end=str(max(r['match'].kickoff.date() for r in validation)),
        criterion='Lowest validation log loss; exact ties prefer Logistic Regression.')


def train(factory, provider="api-football", test_year=None, compare=False):
    with factory() as db:
        if provider == "real":
            all_matches, seasons, sources = real_matches(db)
            if test_year is None:
                raise ValueError("Combined real training requires --test-season (use 2025 for this release).")
            for year in sorted(set(seasons.values())):
                if year <= test_year:
                    require_complete_season(all_matches, seasons, year)
            require_complete_season(all_matches, seasons, test_year)
            matches = [m for m in all_matches if m.status in FINISHED]
        else:
            seasons = {s.id: s.year for s in db.scalars(select(Season).where(Season.provider == provider))}
            matches = list(db.scalars(select(Match).where(Match.provider == provider,
                                Match.status.in_(FINISHED)).order_by(Match.kickoff)))
    if any(m.kickoff >= utcnow() for m in matches):
        raise ValueError("Completed data contains future results; training refused.")
    rows = feature_rows(matches)
    years = sorted({seasons[r["match"].season_id] for r in rows})
    if len(years) < 2:
        raise ValueError("Import at least two seasons with completed results before training.")
    test_year = years[-1] if test_year is None else test_year
    test = [r for r in rows if seasons[r["match"].season_id] == test_year]
    if not test:
        raise ValueError("No eligible fixtures in the requested test season.")
    cutoff = min(r["match"].kickoff for r in test)
    training = [r for r in rows if seasons[r["match"].season_id] < test_year and r["match"].kickoff < cutoff]
    if len(training) < 50 or len(test) < 30:
        raise ValueError("Need at least 50 training and 30 held-out fixtures with sufficient team history.")
    comparison = None
    if compare:
        fitted, predicted, comparison = compare_candidates(training,test)
    else:
        fitted = fit(training)
        predicted = [probabilities(fitted, row["x"]) for row in test]
    prior = {c: sum(r["y"] == c for r in training) / len(training) for c in LABELS}
    report = {"test_year": test_year, "training_years": sorted({seasons[r['match'].season_id] for r in training}),
              "train_count": len(training), "test_count": len(test), "features": FEATURES,
              "model": metrics([r["y"] for r in test], predicted),
              "baseline": metrics([r["y"] for r in test], [prior] * len(test)),
              "predictions": [{"match_id": r["match"].id, "actual": r["y"], "probabilities": p}
                              for r, p in zip(test, predicted)],
              "method": "Fixed logistic regression; final imported season held out. Only earlier UTC dates inform historical form, excluding overlapping same-day games. Earlier test-season results may inform later form, but never model fitting. Production coefficients are subsequently refitted on all completed data."}
    if provider == "real":
        report["sources"] = sources
        report["club_mapping"] = "Explicit EPL name aliases v1; native provider IDs retained."
        report["method"] = ("Fixed logistic regression; explicitly selected test season held out. "
            "Evaluation fitting uses only earlier seasons; current-season results never enter evaluation fitting. "
            "Features use earlier UTC dates only. Production coefficients are separately refitted on all completed real data. "
            "One recorded source per season prevents duplicate matches; club aliases connect form across providers.")
    if comparison:
        report['comparison'] = comparison
        report['algorithm'] = comparison['selected']
        report['method'] = (
            "Logistic Regression and a fixed Random Forest are compared on the last quarter of earlier-season UTC dates. "
            "The lower validation log loss selects the forecasting algorithm before the benchmark season is scored. "
            "Both are refitted on all earlier-season rows for the same benchmark fixtures. "
            "Form uses only earlier UTC dates; earlier benchmark results can inform later form. "
            "The selected algorithm is subsequently refitted on all completed data for future forecasts. "
            "The 2025/26 benchmark has been inspected previously; it is not a new untouched test set.")
    selected_fitter = fit_forest if comparison and comparison['selected'] == 'random_forest' else fit
    with factory.begin() as db:
        run = ModelRun(provider=provider, trained_through=max(m.kickoff for m in matches),
                       parameters=selected_fitter(rows), report=report)
        db.add(run)
        db.flush()
        return run.id, report


def record_forecasts(factory, provider="api-football", now=None):
    now = now or utcnow()
    with factory.begin() as db:
        run = db.scalar(select(ModelRun).where(ModelRun.provider == provider).order_by(ModelRun.id.desc()))
        if run is None:
            raise ValueError("Train a model before recording forecasts.")
        if run.trained_through >= now:
            raise ValueError("Model training cutoff is not before forecast time.")
        if provider == "real":
            matches, _, _ = real_matches(db, run.report["sources"])
        else:
            matches = list(db.scalars(select(Match).where(Match.provider == provider).order_by(Match.kickoff)))
        history = defaultdict(list)
        for m in matches:
            if m.status in FINISHED and m.kickoff < now:
                history[m.home_id].append(result_for(m, m.home_id))
                history[m.away_id].append(result_for(m, m.away_id))
        # At most each team's next fixture: later previews would omit intervening form.
        seen, count = set(), 0
        for m in matches:
            if m.status not in SCHEDULED or m.kickoff <= max(now, run.trained_through):
                continue
            overlaps = m.home_id in seen or m.away_id in seen
            seen.update((m.home_id, m.away_id))
            if overlaps:
                continue
            x = history_features(history, m.home_id, m.away_id)
            if x is None or db.scalar(select(Forecast).where(Forecast.match_id == m.id, Forecast.model_id == run.id)):
                continue
            db.add(Forecast(match_id=m.id, model_id=run.id, created_at=now,
                            kickoff_at_creation=m.kickoff, probabilities=probabilities(run.parameters, x)))
            count += 1
        return count


def tracker(db, provider):
    query = select(Forecast, Match).join(Match, Forecast.match_id == Match.id)
    if provider == "real":
        query = query.join(ModelRun, Forecast.model_id == ModelRun.id).where(ModelRun.provider == "real")
    else:
        query = query.where(Match.provider == provider)
    pairs = db.execute(query.order_by(Forecast.created_at.desc(), Forecast.id.desc())).all()
    chosen = {}
    for forecast, match in pairs:
        if forecast.created_at >= min(match.kickoff, forecast.kickoff_at_creation):
            continue
        chosen.setdefault(match.id, (forecast, match))
    finished = [(f, m) for f, m in chosen.values() if m.status in FINISHED]
    y = ["H" if m.home_score > m.away_score else "D" if m.home_score == m.away_score else "A" for _, m in finished]
    return {"count": len(chosen), "scored": len(finished), "pairs": list(chosen.values()),
            "metrics": metrics(y, [f.probabilities for f, _ in finished]) if finished else None}
