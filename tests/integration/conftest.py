import httpx
import pytest

JENKINS_URL = "http://localhost:8080"


def _jenkins_available() -> bool:
    try:
        httpx.get(JENKINS_URL + "/api/json", auth=("admin", "admin"), timeout=2)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def jenkins_url():
    if not _jenkins_available():
        pytest.skip(
            "docker/jenkins-test isn't running at localhost:8080 -- start it with "
            "`cd docker/jenkins-test && docker compose up -d --build`"
        )
    return JENKINS_URL
