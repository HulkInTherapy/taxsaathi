"""
Intent classification: is the user asking a question, asking for a tax calculation, or asking
something we should not answer (out_of_scope)?

Model = TF-IDF features (word 1-2 grams + character 2-5 grams, which cope with Hinglish
spelling variants) fed into Logistic Regression, trained on data/eval/intent_train.jsonl
(written separately from the gold test questions to avoid leakage). A small rule layer runs
on top: prompt-injection patterns force out_of_scope, and "calculation" needs an amount.

Train:  python -m src.guardrails.intent --train
"""
from __future__ import annotations

import argparse
import json
import re
import threading

from src import config
from src.nlp.entities import extract_amounts

LABELS = ["question", "calculation", "out_of_scope"]

# Attempts to override the system's instructions -> always out of scope.
INJECTION_RE = re.compile(
    r"ignore\s+(all\s+|the\s+|your\s+|any\s+)?(previous|prior|above|earlier)?\s*(instructions|rules|prompts?)|"
    r"disregard\s+(the\s+|all\s+|your\s+)?(previous|above|system)|system\s+prompt|"
    r"you\s+are\s+now\s+|act\s+as\s+(an?\s+)?(unrestricted|dan|jailbroken)|jailbreak|"
    r"pretend\s+(you\s+are|to\s+be)|forget\s+(all\s+|your\s+)?(rules|instructions)|"
    r"reveal\s+(your\s+)?(prompt|instructions)|developer\s+mode|"
    r"pichle\s+(saare\s+)?instructions?\s+(bhool|ignore)",
    re.IGNORECASE)
CALC_HINT_RE = re.compile(
    r"calculat|comput|how\s+much\s+(income\s+)?tax|kitna\s+tax|tax\s+kitna|tax\s+liability|"
    r"which\s+regime\s+(is\s+)?(better|best)|compare|better\s+for\s+me|kaunsa\s+regime|"
    r"tax\s+on\s+(my\s+)?(salary|income)|my\s+tax|total\s+tax|payable", re.IGNORECASE)

_MODEL = None
_LOCK = threading.Lock()


def build_model():
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion, Pipeline
    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True,
                                 token_pattern=r"(?u)\b\w+\b", sublinear_tf=True, min_df=1)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True,
                                 sublinear_tf=True, min_df=1)),
    ])
    return Pipeline([("features", features),
                     ("clf", LogisticRegression(C=10.0, max_iter=2000, class_weight="balanced"))])


def load_training(path=None) -> tuple[list[str], list[str]]:
    path = path or config.INTENT_TRAIN_PATH
    texts, labels = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                texts.append(row["text"])
                labels.append(row["label"])
    return texts, labels


def train(save: bool = True, verbose: bool = True):
    """Fit on all rows, print 5-fold cross-validation accuracy, save to data/processed/intent.joblib."""
    import joblib
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    texts, labels = load_training()
    if verbose:
        from collections import Counter
        print(f"training rows: {len(texts)}  {dict(Counter(labels))}")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(build_model(), texts, labels, cv=cv, scoring="accuracy")
        print(f"5-fold CV accuracy: {scores.mean():.3f} ± {scores.std():.3f}")
    model = build_model().fit(texts, labels)
    if save:
        config.INTENT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, config.INTENT_MODEL_PATH)
        if verbose:
            print(f"saved {config.INTENT_MODEL_PATH}")
    return model


def get_model():
    """Load the saved model, or train it on the fly if the .joblib file is missing."""
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            if config.INTENT_MODEL_PATH.exists():
                import joblib
                _MODEL = joblib.load(config.INTENT_MODEL_PATH)
            else:
                _MODEL = train(save=True, verbose=False)
    return _MODEL


def classify(text: str) -> dict:
    """Return {"label", "probs": {label: p}, "rule": str|None}."""
    if INJECTION_RE.search(text):
        return {"label": "out_of_scope", "probs": {"question": 0.0, "calculation": 0.0, "out_of_scope": 1.0},
                "rule": "prompt-injection pattern"}
    model = get_model()
    p = model.predict_proba([text])[0]
    probs = {lab: float(v) for lab, v in zip(model.classes_, p)}
    label = max(probs, key=probs.get)
    rule = None
    has_amount = bool(extract_amounts(text))
    if label == "calculation" and not has_amount and not CALC_HINT_RE.search(text):
        label, rule = "question", "calculation needs an amount or a compute request"
    elif label == "question" and has_amount and CALC_HINT_RE.search(text) and probs.get("out_of_scope", 0) < 0.5:
        label, rule = "calculation", "amount + compute wording"
    return {"label": label, "probs": {k: round(v, 4) for k, v in probs.items()}, "rule": rule}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Train / try the intent classifier")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--query", help="classify one query")
    a = ap.parse_args()
    if a.train or not a.query:
        train()
    if a.query:
        print(classify(a.query))
