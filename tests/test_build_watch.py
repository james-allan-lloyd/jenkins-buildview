from types import SimpleNamespace

import httpx

from buildview.screens.build_watch import BuildWatchScreen


class FakeConsole:
    def __init__(self):
        self.appended = []
        self.titles = []

    def append(self, text):
        self.appended.append(text)

    def clear(self):
        self.appended = []

    def set_title(self, title=None):
        self.titles.append(title)

    def push_focus(self, prev_focus):
        pass


def make_screen(client: httpx.AsyncClient, fake_console: FakeConsole) -> BuildWatchScreen:
    screen = BuildWatchScreen("http://fake/job/x", client, allow_back=False)
    screen.latest_build_url = "http://fake/job/x/1"
    screen.query_one = lambda *a, **k: fake_console
    return screen


async def test_tail_stage_log_merges_growing_log_across_polls():
    full_text = "".join(f"line {i}\n" for i in range(2000))
    growth_points = [500, 3000, 8000, len(full_text)]
    call_count = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        cutoff = growth_points[min(call_count["n"] - 1, len(growth_points) - 1)]
        text = full_text[:cutoff]
        chunk_size = 137  # deliberately misaligned with growth_points, to
        # exercise the case where a chunk straddles the already-seen boundary

        async def gen():
            for i in range(0, len(text), chunk_size):
                yield text[i : i + chunk_size].encode()

        return httpx.Response(200, content=gen())

    fake_console = FakeConsole()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://fake")
    screen = make_screen(client, fake_console)
    screen.viewing_stage_id = "n1"

    try:
        for cutoff in growth_points:
            await screen._tail_stage_log("n1")
            expected = full_text[:cutoff]
            assert screen.log_cache["n1"] == expected
            assert "".join(fake_console.appended) == expected
    finally:
        await client.aclose()


async def test_tail_stage_log_does_not_append_when_viewing_a_different_stage():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="hello world")),
        base_url="http://fake",
    )
    screen = make_screen(client, fake_console)
    screen.viewing_stage_id = "other-stage"

    try:
        await screen._tail_stage_log("n1")
        assert screen.log_cache["n1"] == "hello world"
        assert fake_console.appended == []
    finally:
        await client.aclose()


async def test_tail_stage_log_only_appends_the_new_suffix_when_cache_is_warm():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="abcdef")),
        base_url="http://fake",
    )
    screen = make_screen(client, fake_console)
    screen.viewing_stage_id = "n1"
    screen.log_cache["n1"] = "abc"

    try:
        await screen._tail_stage_log("n1")
        assert screen.log_cache["n1"] == "abcdef"
        assert fake_console.appended == ["def"]
    finally:
        await client.aclose()


async def test_selecting_a_finished_stage_shows_its_cached_log_and_stops_following():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200)), base_url="http://fake"
    )
    screen = make_screen(client, fake_console)
    screen.current_stage_id = "running-stage"
    screen.log_cache["finished-stage"] = "some finished output"

    try:
        node = SimpleNamespace(data={"id": "finished-stage", "name": "Finished Stage"})
        screen.on_tree_node_selected(SimpleNamespace(node=node))

        assert screen.following_latest is False
        assert screen.viewing_stage_id == "finished-stage"
        assert fake_console.appended == ["some finished output"]
    finally:
        await client.aclose()


async def test_show_stage_log_lazily_fetches_an_uncached_non_live_stage():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200)), base_url="http://fake"
    )
    screen = make_screen(client, fake_console)
    screen.current_stage_id = None  # nothing currently live

    fetched = []
    screen._fetch_stage_log_once = lambda node_id: fetched.append(node_id)

    try:
        screen.show_stage_log({"id": "old-stage", "name": "Old Stage"})
        assert fetched == ["old-stage"]
        assert screen.viewing_stage_id == "old-stage"
    finally:
        await client.aclose()


async def test_show_stage_log_does_not_fetch_the_stage_already_being_tailed():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200)), base_url="http://fake"
    )
    screen = make_screen(client, fake_console)
    screen.current_stage_id = "live-stage"

    fetched = []
    screen._fetch_stage_log_once = lambda node_id: fetched.append(node_id)

    try:
        screen.show_stage_log({"id": "live-stage", "name": "Live Stage"})
        # watch_stage()'s own polling loop is already tailing this stage --
        # a separate one-off fetch here would just race it.
        assert fetched == []
    finally:
        await client.aclose()


async def test_show_stage_log_does_not_refetch_an_already_cached_stage():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200)), base_url="http://fake"
    )
    screen = make_screen(client, fake_console)
    screen.current_stage_id = None
    screen.log_cache["old-stage"] = "already downloaded"

    fetched = []
    screen._fetch_stage_log_once = lambda node_id: fetched.append(node_id)

    try:
        screen.show_stage_log({"id": "old-stage", "name": "Old Stage"})
        assert fetched == []
        assert fake_console.appended == ["already downloaded"]
    finally:
        await client.aclose()


async def test_selecting_the_running_stage_resumes_following():
    fake_console = FakeConsole()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200)), base_url="http://fake"
    )
    screen = make_screen(client, fake_console)
    screen.current_stage_id = "running-stage"
    screen.following_latest = False
    screen.log_cache["running-stage"] = "live output so far"

    try:
        node = SimpleNamespace(data={"id": "running-stage", "name": "Running Stage"})
        screen.on_tree_node_selected(SimpleNamespace(node=node))

        assert screen.following_latest is True
        assert screen.viewing_stage_id == "running-stage"
    finally:
        await client.aclose()
