import asyncio
from dataclasses import dataclass

import httpx

PATH_SEPARATOR = " » "


@dataclass
class JobEntry:
    name: str
    url: str
    path: str


def _api_json_url(url: str) -> str:
    if not url.endswith("/"):
        url += "/"
    return url + "api/json"


async def _fetch_jobs_recursive(
    client: httpx.AsyncClient, url: str, path_parts: list[str]
) -> list[JobEntry]:
    response = await client.get(_api_json_url(url), params={"tree": "jobs[name,url,color]"})
    data = response.json()

    leaves: list[JobEntry] = []
    folder_fetches = []

    for job in data.get("jobs", []):
        job_path = path_parts + [job["name"]]
        if "color" in job:
            leaves.append(
                JobEntry(name=job["name"], url=job["url"], path=PATH_SEPARATOR.join(job_path))
            )
        else:
            folder_fetches.append(_fetch_jobs_recursive(client, job["url"], job_path))

    if folder_fetches:
        for nested in await asyncio.gather(*folder_fetches):
            leaves.extend(nested)

    return leaves


async def fetch_jobs(client: httpx.AsyncClient, base_url: str) -> list[JobEntry]:
    """Recursively fetch all buildable jobs under `base_url`, including
    those nested in folders and multibranch pipelines."""
    return await _fetch_jobs_recursive(client, base_url, [])


def filter_jobs(jobs: list[JobEntry], query: str) -> list[JobEntry]:
    query = query.strip().lower()
    if not query:
        return jobs
    return [job for job in jobs if query in job.path.lower()]
