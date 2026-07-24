import httpx
import pytest

from buildview.jobs import JobEntry, fetch_jobs, filter_jobs

BASE = "https://jenkins.example.com"


def make_client(routes: dict):
    def handler(request):
        path = request.url.path
        if path in routes:
            return httpx.Response(200, json=routes[path])
        return httpx.Response(404)

    return httpx.AsyncClient(base_url=BASE, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fetch_jobs_returns_top_level_leaf_jobs():
    routes = {
        "/api/json": {
            "jobs": [
                {"name": "job1", "url": f"{BASE}/job/job1/", "color": "blue"},
            ]
        }
    }
    async with make_client(routes) as client:
        jobs = await fetch_jobs(client, BASE)

    assert jobs == [JobEntry(name="job1", url=f"{BASE}/job/job1/", path="job1")]


@pytest.mark.asyncio
async def test_fetch_jobs_recurses_into_folders_and_multibranch_projects():
    routes = {
        "/api/json": {
            "jobs": [
                {"name": "folder1", "url": f"{BASE}/job/folder1/"},
                {"name": "job1", "url": f"{BASE}/job/job1/", "color": "blue"},
            ]
        },
        "/job/folder1/api/json": {
            "jobs": [
                {"name": "pipeline", "url": f"{BASE}/job/folder1/job/pipeline/"},
            ]
        },
        "/job/folder1/job/pipeline/api/json": {
            "jobs": [
                {
                    "name": "main",
                    "url": f"{BASE}/job/folder1/job/pipeline/job/main/",
                    "color": "blue",
                },
                {
                    "name": "feature-x",
                    "url": f"{BASE}/job/folder1/job/pipeline/job/feature-x/",
                    "color": "yellow",
                },
            ]
        },
    }

    async with make_client(routes) as client:
        jobs = await fetch_jobs(client, BASE)

    paths = {job.path: job.url for job in jobs}
    assert paths == {
        "job1": f"{BASE}/job/job1/",
        "folder1 » pipeline » main": f"{BASE}/job/folder1/job/pipeline/job/main/",
        "folder1 » pipeline » feature-x": f"{BASE}/job/folder1/job/pipeline/job/feature-x/",
    }


def test_filter_jobs_matches_case_insensitive_substring_anywhere_in_path():
    jobs = [
        JobEntry(name="main", url="u1", path="org » repo » main"),
        JobEntry(name="feature-x", url="u2", path="org » repo » feature-x"),
        JobEntry(name="other", url="u3", path="org » other-repo » main"),
    ]

    assert filter_jobs(jobs, "REPO") == jobs
    assert filter_jobs(jobs, "feature") == [jobs[1]]
    assert filter_jobs(jobs, "") == jobs
    assert filter_jobs(jobs, "nonexistent") == []
