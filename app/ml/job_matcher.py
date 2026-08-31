"""Ranks open jobs against a candidate's resume text, for the Jobs page
and the 'match %' badge shown on each job card.
"""

from app.ml.ats_scorer import score_resume


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
        jd_text = " ".join(filter(None, [job.description, job.requirements]))
        result = score_resume(resume_text, jd_text)
        results.append((job, result["score"]))

    results.sort(key=lambda pair: (pair[1] if pair[1] is not None else -1), reverse=True)
    return results


def match_breakdown(resume_text, job):
    """Full matched/missing keyword breakdown for a single job detail page."""
    jd_text = " ".join(filter(None, [job.description, job.requirements]))
    return score_resume(resume_text, jd_text)
