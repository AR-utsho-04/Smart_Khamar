"""Train the disease-risk model.  Run:  python -m app.ml.train"""
import json
from datetime import datetime, timezone
import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import settings
from .features import CAT_COLS, NUM_COLS, SYMPTOMS, FEATURE_COLS
from .generate_data import generate


def build_pipeline(estimator, scale=False):
    num = [("imp", SimpleImputer(strategy="median"))] + ([("sc", StandardScaler())] if scale else [])
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ("num", Pipeline(num), NUM_COLS),
        ("sym", "passthrough", SYMPTOMS),
    ])
    return Pipeline([("pre", pre), ("clf", estimator)])


def train(n_rows=6000, model_dir=None, verbose=True):
    model_dir = model_dir or settings.MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    df = generate(n_rows)
    X, y = df[FEATURE_COLS], df["label"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    candidates = {
        "Logistic Regression": build_pipeline(LogisticRegression(max_iter=1000), scale=True),
        "Random Forest": build_pipeline(RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)),
        "Gradient Boosting": build_pipeline(GradientBoostingClassifier(n_estimators=100, random_state=42)),
    }
    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    results = {}
    for name, pipe in candidates.items():
        cv_f1 = float(np.mean(cross_val_score(pipe, X_tr, y_tr, cv=cv, scoring="f1_macro", n_jobs=-1)))
        pipe.fit(X_tr, y_tr)
        pred = pipe.predict(X_te)
        results[name] = {
            "cv_macro_f1": round(cv_f1, 4),
            "test_accuracy": round(float(accuracy_score(y_te, pred)), 4),
            "test_macro_f1": round(float(f1_score(y_te, pred, average="macro")), 4),
        }
        if verbose:
            print(f"{name:22s} CV macro-F1={cv_f1:.3f}  test macro-F1={results[name]['test_macro_f1']:.3f}")

    best = max(results, key=lambda k: results[k]["cv_macro_f1"])
    final = CalibratedClassifierCV(candidates[best], method="sigmoid", cv=3)  # calibrated probabilities
    final.fit(X_tr, y_tr)
    pred = final.predict(X_te)
    labels = list(final.classes_)
    metrics = {
        "model_version": "v1",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_data": True,
        "n_rows": int(n_rows),
        "models": results,
        "chosen_model": best,
        "final": {
            "accuracy": round(float(accuracy_score(y_te, pred)), 4),
            "macro_precision": round(float(precision_score(y_te, pred, average="macro", zero_division=0)), 4),
            "macro_recall": round(float(recall_score(y_te, pred, average="macro", zero_division=0)), 4),
            "macro_f1": round(float(f1_score(y_te, pred, average="macro")), 4),
            "per_class": classification_report(y_te, pred, output_dict=True, zero_division=0),
            "confusion_matrix": {"labels": labels, "matrix": confusion_matrix(y_te, pred, labels=labels).tolist()},
        },
    }
    joblib.dump({"pipeline": final, "classes": labels, "version": "v1"}, model_dir / "model.joblib")
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if verbose:
        print(f"\nChosen: {best}.  Final test accuracy={metrics['final']['accuracy']}  macro-F1={metrics['final']['macro_f1']}")
        print(f"Saved model to {model_dir}")
    from .anomaly import train_anomaly
    train_anomaly(model_dir, verbose=verbose)
    return metrics


if __name__ == "__main__":
    train()
