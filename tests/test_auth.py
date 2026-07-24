import json

import httpx
import pytest

from buildview.auth import CredentialStore, Credentials, validate


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def get_password(self, service, account):
        return self.store.get((service, account))

    def set_password(self, service, account, password):
        self.store[(service, account)] = password

    def delete_password(self, service, account):
        del self.store[(service, account)]


def make_store(tmp_path, keyring_backend=None):
    return CredentialStore(
        path=tmp_path / "config.json", keyring_backend=keyring_backend or FakeKeyring()
    )


def test_load_returns_none_when_no_config_file(tmp_path):
    store = make_store(tmp_path)
    assert store.load() is None


def test_save_then_load_round_trips_credentials(tmp_path):
    store = make_store(tmp_path)
    creds = Credentials(server="https://jenkins.example.com", username="alice", token="secret")

    store.save(creds)
    loaded = store.load()

    assert loaded == creds


def test_config_file_does_not_contain_token(tmp_path):
    store = make_store(tmp_path)
    creds = Credentials(server="https://jenkins.example.com", username="alice", token="secret")

    store.save(creds)

    data = json.loads(store.path.read_text())
    assert "token" not in data
    assert "secret" not in store.path.read_text()


def test_load_returns_none_when_token_missing_from_keyring(tmp_path):
    store = make_store(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(json.dumps({"server": "https://jenkins.example.com", "username": "alice"}))

    assert store.load() is None


def test_clear_removes_config_and_token(tmp_path):
    store = make_store(tmp_path)
    creds = Credentials(server="https://jenkins.example.com", username="alice", token="secret")
    store.save(creds)

    store.clear()

    assert not store.path.exists()
    assert store.load() is None


@pytest.mark.asyncio
async def test_validate_returns_true_for_200():
    def handler(request):
        assert request.url.path == "/whoAmI/api/json"
        return httpx.Response(200, json={"name": "alice"})

    async with httpx.AsyncClient(
        base_url="https://jenkins.example.com", transport=httpx.MockTransport(handler)
    ) as client:
        assert await validate(client) is True


@pytest.mark.asyncio
async def test_validate_returns_false_for_401():
    def handler(request):
        return httpx.Response(401)

    async with httpx.AsyncClient(
        base_url="https://jenkins.example.com", transport=httpx.MockTransport(handler)
    ) as client:
        assert await validate(client) is False


@pytest.mark.asyncio
async def test_validate_returns_false_on_network_error():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    async with httpx.AsyncClient(
        base_url="https://jenkins.example.com", transport=httpx.MockTransport(handler)
    ) as client:
        assert await validate(client) is False
