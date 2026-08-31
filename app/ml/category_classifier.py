"""Classifies a resume into a job category when the candidate hasn't pasted
a job description — so the ATS checker still has something to score against.

Trained on app/ml/data/resumes_dataset.csv (360 labelled resumes, 8 balanced
categories). Algorithm: TF-IDF + Multinomial Naive Bayes — the simplest of
the three models tested (NB, Logistic Regression, Linear SVC); all three
hit 100% cross-validated accuracy on this dataset, so the simplest one wins.

The model trains once, lazily, on first use (360 rows -> well under a
second) and stays cached in memory for the life of the process.
"""

import os

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

_DATASET_PATH = os.path.join(os.path.dirname(__file__), "data", "resumes_dataset.csv")

_pipeline = None          # cached trained Pipeline
_category_profiles = None  # {category: representative_text} for JD fallback


def _train():
    global _pipeline, _category_profiles

    df = pd.read_csv(_DATASET_PATH)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)),
        ("clf", MultinomialNB()),
    ])
    pipeline.fit(df["resume_text"], df["category"])

    # Build one "reference" text per category by concatenating every resume
    # in that category — this stands in for a job description when the
    # candidate hasn't provided one, so ats_scorer can still compute a
    # meaningful match score and keyword list.
    profiles = (
        df.groupby("category")["resume_text"]
        .apply(lambda texts: " ".join(texts))
        .to_dict()
    )

    _pipeline = pipeline
    _category_profiles = profiles


def _ensure_trained():
    if _pipeline is None:
        _train()


def predict_category(resume_text):
    """Return the most likely job category for a resume's text."""
    _ensure_trained()
    if not resume_text or not resume_text.strip():
        return None
    return _pipeline.predict([resume_text])[0]


def category_reference_text(category):
    """Return the aggregated reference text for a category, for use as a
    stand-in job description in ats_scorer.score_resume().
    """
    _ensure_trained()
    return _category_profiles.get(category, "")


def top_categories(resume_text, n=3):
    """Return the top-n (category, probability) pairs, most likely first —
    used if we want to show 'this looks like a Software Engineer resume'
    with a confidence level.
    """
    _ensure_trained()
    if not resume_text or not resume_text.strip():
        return []
    proba = _pipeline.predict_proba([resume_text])[0]
    classes = _pipeline.classes_
    ranked = sorted(zip(classes, proba), key=lambda pair: pair[1], reverse=True)
    return ranked[:n]
