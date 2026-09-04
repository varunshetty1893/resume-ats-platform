"""Ranks open jobs against a candidate's resume text, for the Jobs page
and the 'match %' badge shown on each job card.
"""

from app.ml.ats_scorer import score_resume_for_job


def rank_jobs_for_resume(resume_text, jobs):
    """Given a resume's text and a list of Job objects, return a list of
    (job, match_score) tuples sorted by score descending.

    If resume_text is empty, every job gets a score of None so the UI can
    fall back to showing plain listings.
    """
    if not resume_text:
        return [(job, None) for job in jobs]

    results = []
    for job in jobs:
        result = score_resume_for_job(resume_text, job)
        results.append((job, result["score"]))

    results.sort(key=lambda pair: (pair[1] if pair[1] is not None else -1), reverse=True)
    return results


def match_breakdown(resume_text, job):
    """Full matched/missing keyword breakdown for a single job detail page."""
    return score_resume_for_job(resume_text, job)


def rank_and_explain_jobs(resume_text, jobs):
    """Single-pass scoring for the Jobs listing page.

    Calls score_resume_for_job() exactly ONCE per job and returns:
      - ranked_jobs : list of (job, score) sorted by score desc
      - match_explanations : dict mapping job.id -> full score_resume result

    This replaces the old two-pass pattern where rank_jobs_for_resume()
    and match_breakdown() each called score_resume() separately.
    """
    if not resume_text:
        return [(job, None) for job in jobs], {}

    scored = []
    explanations = {}
    for job in jobs:
        result = score_resume_for_job(resume_text, job)   # called ONCE
        scored.append((job, result["score"]))
        explanations[job.id] = result

    scored.sort(key=lambda pair: (pair[1] if pair[1] is not None else -1), reverse=True)
    return scored, explanations
