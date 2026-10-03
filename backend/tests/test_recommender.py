import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from recommender import recommend

JOBS = [
    dict(id=1, title="Python Developer", description="Build APIs with Flask", skills=["Python", "Flask", "SQL"], location="Hyderabad", job_type="Full-time", exp_min=0),
    dict(id=2, title="Frontend Developer", description="Build UIs with React", skills=["React", "JavaScript", "CSS"], location="Bangalore", job_type="Full-time", exp_min=1),
    dict(id=3, title="DevOps Engineer", description="Automate deployments", skills=["Docker", "AWS", "Linux"], location="Remote", job_type="Full-time", exp_min=3),
]


def user(**kw):
    base = dict(skills=[], text="", exp=1, locations=[], roles=[], job_type="")
    base.update(kw)
    return base


def test_backend_user_ranks_python_job_first():
    res = recommend(user(skills=["Python", "Flask", "SQL"], roles=["Backend Developer"]), JOBS)
    assert res[0]["title"] == "Python Developer"
    assert res[0]["match"] > res[-1]["match"]


def test_frontend_user_ranks_frontend_job_first():
    res = recommend(user(skills=["React", "JavaScript", "CSS"], roles=["Frontend Developer"]), JOBS)
    assert res[0]["title"] == "Frontend Developer"


def test_explanations_and_missing_skills():
    res = recommend(user(skills=["Python", "Flask"]), JOBS)
    top = res[0]
    assert top["matched"] == ["flask", "python"] and top["missing"] == ["sql"]


def test_no_matching_skills_gives_low_score():
    res = recommend(user(skills=["Cooking"]), JOBS)
    assert all(r["match"] < 40 for r in res)


def test_empty_job_list():
    assert recommend(user(skills=["Python"]), []) == []
