"""Bounded Random Forest with portable JSON inference, no pickle loading."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from .analytics import FEATURES

SETTINGS = dict(n_estimators=150, max_depth=5, min_samples_leaf=12,
                max_features='sqrt', random_state=42, n_jobs=1)


def fit_forest(rows):
    x = np.asarray([r['x'] for r in rows],dtype=np.float32)
    y = [r['y'] for r in rows]
    if set(y) != {'A','D','H'}:
        raise ValueError('Training requires all three match outcomes.')
    model = RandomForestClassifier(**SETTINGS).fit(x,y)
    trees=[]
    for estimator in model.estimators_:
        t=estimator.tree_
        values=t.value[:,0,:]
        values=values/values.sum(axis=1,keepdims=True)
        trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),
                          feature=t.feature.tolist(),threshold=t.threshold.tolist(),values=values.tolist()))
    return dict(algorithm='random_forest',features=FEATURES,classes=model.classes_.tolist(),
                settings=SETTINGS,trees=trees,importance=model.feature_importances_.tolist())


def forest_probabilities(parameters,x):
    x=np.asarray(x,dtype=np.float32)
    if x.shape != (len(parameters['features']),) or not np.isfinite(x).all():
        raise ValueError('Invalid match feature vector.')
    result=np.zeros(len(parameters['classes']))
    for tree in parameters['trees']:
        node=0
        while tree['left'][node] != -1:
            node=(tree['left'][node] if x[tree['feature'][node]] <= tree['threshold'][node]
                  else tree['right'][node])
        result+=tree['values'][node]
    result/=len(parameters['trees'])
    return dict(zip(parameters['classes'],result.tolist()))
