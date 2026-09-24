"""Interpretable Linear Regression baseline; chronological evaluation, JSON weights."""
from io import BytesIO
import hashlib
import json
import math
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sqlalchemy import select
from .value_data import POSITIONS, prepare_dataset, load_prepared
from .storage import ValueModel

NUMERIC = ['goals','assists','minutes','age']
FEATURES = NUMERIC + ['position']
MODEL_VERSION = 1


def metrics(actual, predicted):
    return dict(mae_eur=float(mean_absolute_error(actual,predicted)),
                rmse_eur=float(np.sqrt(mean_squared_error(actual,predicted))),
                r2=float(r2_score(actual,predicted)))


def train_value_model(factory, folder=None, first_season=2021, test_season=2025):
    rows, manifest = (load_prepared(first_season=first_season,last_season=test_season) if folder is None
                      else prepare_dataset(folder, first_season, test_season))
    return fit_value_model(factory, rows, manifest, test_season)


def fit_value_model(factory, rows, manifest, test_season):
    training = rows[rows.season < test_season].copy()
    test = rows[rows.season == test_season].copy()
    if len(training) < 200 or len(test) < 50 or training.season.nunique() < 2:
        raise ValueError('Need 200+ labelled training rows across two earlier seasons and 50+ in the test season. Choose an earlier --test-season if recent valuations are incomplete.')
    if training.valuation_date.max() >= test.valuation_date.min():
        raise ValueError('Training valuations overlap the test period.')
    if (rows.stats_through >= rows.valuation_date).any():
        raise ValueError('Statistics must strictly precede each valuation.')
    if set(training.position.unique()) != set(POSITIONS):
        raise ValueError('Training data must cover all four player positions.')
    # No current value, player ID, name, future stats or test labels are features.
    preprocessor = ColumnTransformer([
        ('numeric', StandardScaler(), NUMERIC),
        ('position', OneHotEncoder(categories=[POSITIONS], drop='first', handle_unknown='error', sparse_output=False), ['position'])])
    pipeline = make_pipeline(preprocessor, LinearRegression())
    pipeline.fit(training[FEATURES], training.actual_eur)
    raw = pipeline.predict(test[FEATURES])
    predicted = np.maximum(0, raw)
    baseline = np.full(len(test), training.actual_eur.median())
    scaler = preprocessor.named_transformers_['numeric']
    reg = pipeline.named_steps['linearregression']
    params = {'version':MODEL_VERSION,'numeric':NUMERIC,'means':scaler.mean_.tolist(),
              'scales':scaler.scale_.tolist(),'positions':POSITIONS,'coefficients':reg.coef_.tolist(),
              'intercept':float(reg.intercept_),
              'ranges':{key:[float(training[key].min()),float(training[key].max())] for key in NUMERIC}}
    examples = []
    for (_, row), estimate in zip(test.iterrows(), predicted):
        entry = {key: (float(row[key]) if key in NUMERIC + ['actual_eur'] else str(row[key])) for key in FEATURES + ['actual_eur','name','player_id']}
        entry.update(season=int(row.season), valuation_date=str(row.valuation_date.date()),
                     stats_through=str(row.stats_through.date()), predicted_eur=float(estimate),
                     error_eur=float(estimate-row.actual_eur), appearance_count=int(row.appearance_count))
        examples.append(entry)
    report = {'model':metrics(test.actual_eur,predicted), 'baseline':metrics(test.actual_eur,baseline),
              'baseline_median_eur':float(training.actual_eur.median()), 'train_count':len(training), 'test_count':len(test),
              'train_seasons':sorted(int(y) for y in training.season.unique()),'test_season':test_season,
              'train_through':str(training.valuation_date.max().date()),
              'test_from':str(test.valuation_date.min().date()), 'test_through':str(test.valuation_date.max().date()),
              'negative_predictions_clipped':int((raw<0).sum()),
              'returning_players':int(test.player_id.isin(training.player_id).sum()),
              'manifest':manifest}
    signature = {'data':rows.to_csv(index=False),'first_season':int(training.season.min()),
                 'test_season':test_season,'version':MODEL_VERSION}
    digest = hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
    with factory.begin() as db:
        existing = db.scalar(select(ValueModel).where(ValueModel.dataset_hash == digest))
        if existing:
            return existing.id, existing.report
        model = ValueModel(dataset_hash=digest,parameters=params,report=report,examples=examples)
        db.add(model); db.flush()
        return model.id, report


def estimate_value(parameters, inputs):
    values, warnings = [], []
    limits = {'goals':(0,100), 'assists':(0,100), 'minutes':(450,5000), 'age':(16,45)}
    for key in NUMERIC:
        try:
            value = float(inputs[key])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f'Enter a valid {key} value.') from None
        lo, hi = limits[key]
        if not math.isfinite(value) or not lo <= value <= hi or (key != 'age' and value % 1):
            raise ValueError(f'{key.title()} must be between {lo} and {hi}' + (' and a whole number.' if key != 'age' else '.'))
        values.append(value)
        a,b = parameters['ranges'][key]
        if not a <= value <= b:
            warnings.append(f'{key.title()} is outside the range seen during training.')
    position = inputs.get('position')
    if position not in parameters['positions']:
        raise ValueError('Choose one of the four supported positions.')
    encoded = ((np.array(values)-parameters['means'])/parameters['scales']).tolist()
    encoded += [float(position == p) for p in parameters['positions'][1:]]
    raw = float(np.dot(encoded, parameters['coefficients']) + parameters['intercept'])
    if not math.isfinite(raw):
        raise ValueError('Model could not produce a finite estimate.')
    if raw < 0:
        warnings.append('The linear baseline produced a negative estimate, displayed as €0. This profile is poorly represented by this model.')
    return max(0,raw), warnings


def plot_bytes(model):
    # Agg-backed Figure avoids a display server and pyplot global figure state.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    actual = np.array([p['actual_eur'] for p in model.examples]) / 1e6
    predicted = np.array([p['predicted_eur'] for p in model.examples]) / 1e6
    fig = Figure(figsize=(8,5),dpi=140,layout='constrained',facecolor='#141c2b')
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.set_facecolor('#141c2b')
    ax.tick_params(colors='#a0adc2')
    for spine in ax.spines.values():
        spine.set_color('#39445a')
    ax.scatter(actual,predicted,s=22,color='#c6f65d',alpha=.65,edgecolors='none')
    top = max(float(actual.max()),float(predicted.max())) * 1.04
    ax.plot([0,top],[0,top],color='#aa91ff',linestyle='--',label='Perfect agreement')
    ax.set(xlabel='Recorded market valuation (€ million)',ylabel='Predicted market value (€ million)',
           title=f"Held-out {model.report['test_season']}/{model.report['test_season']+1} player valuations",xlim=(0,top),ylim=(0,top))
    ax.xaxis.label.set_color('#d8e2f1'); ax.yaxis.label.set_color('#d8e2f1')
    ax.title.set_color('#f1f4fa')
    ax.grid(alpha=.18,color='#a0adc2');ax.legend(frameon=False,labelcolor='#d8e2f1')
    output=BytesIO();fig.savefig(output,format='png');output.seek(0)
    return output
