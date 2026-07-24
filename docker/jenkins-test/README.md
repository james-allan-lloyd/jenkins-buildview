# Jenkins test environment for buildview

A disposable, local Jenkins instance for testing/developing `buildview`
against, pre-loaded with a pipeline job (`parallel-nested-demo`) that has
nested and parallel stages.

## Usage

```shell
cd docker/jenkins-test
docker compose up -d --build
```

Wait ~10-20s for Jenkins to finish initializing, then:

- UI: http://localhost:8080 (user: `admin`, password: `admin`)
- The `parallel-nested-demo` job is created automatically via
  `init.groovy.d/seed-job.groovy` from `pipelines/Jenkinsfile.demo`.
- Auth for `buildview`/curl: HTTP basic auth with `admin` / `admin` works
  directly (CSRF protection is disabled via `JAVA_OPTS` for convenience, and
  the local security realm accepts the plain password over basic auth, so
  there's no need to mint a separate API token for this throwaway instance).

Trigger a build:

```shell
curl -u admin:admin -X POST 'http://localhost:8080/job/parallel-nested-demo/build?delay=0sec'
```

Point buildview at it directly:

```shell
echo 'USERNAME=admin
TOKEN=admin' > ../../.env
poetry run jenkins-buildview http://localhost:8080/job/parallel-nested-demo
```

Tear down:

```shell
docker compose down        # keep the named volume (jenkins_home)
docker compose down -v     # also delete it (full reset)
```

## Root cause of "the API no longer works"

Confirmed against this environment (Jenkins 2.541.3, current plugin
versions as of 2026-07): `buildview` is coded against the **old**
`pipeline-stage-view` plugin's `wfapi` REST API
(`buildview/screens/build_watch.py`), which no longer ships at all —
`workflow-aggregator` no longer pulls it in, and it isn't installed here.

- `GET <build>/wfapi/describe` → **404** (endpoint doesn't exist)
- `GET <build>/pipeline-overview/log?nodeId=&startByte=` → **404**

Jenkins replaced the old Stage View with the **`pipeline-graph-view`**
plugin (bundled as a `workflow-aggregator` dependency now), which exposes a
differently-shaped REST API mounted under `<build>/stages/*`
(OpenAPI spec: https://github.com/jenkinsci/pipeline-graph-view-plugin/blob/main/openapi.yaml).
Verified live against `parallel-nested-demo`:

- `GET <build>/stages/tree` → 200, replaces `wfapi/describe`. Shape:
  `{"status": "ok", "data": {"complete": bool, "stages": [Stage, ...]}}`.
  Nested/parallel stages are `children: [Stage, ...]` on each stage — no
  separate flow-node-list fetch needed. Stages use `state` (lowercase enum:
  `queued`/`running`/`paused`/`skipped`/`success`/`unstable`/`failure`/
  `aborted`/...) instead of the old `status` (`SUCCESS`/`FAILED`/
  `IN_PROGRESS`), and there's no `_links` HAL wrapper or `error.message`
  field (see `/exceptionText?nodeId=` for failure details instead).
- `GET <build>/stages/log?nodeId=<id>` → 200, plain text. Replaces
  `pipeline-overview/log`. Takes only `nodeId` — **no `startByte`/offset
  param**, it always returns the full text for that node, so incremental
  tailing needs a different strategy (e.g. diff against the last fetched
  text, or re-render).
- `GET <build>/stages/steps?nodeId=<id>` → per-stage step list (replaces
  `stageFlowNodes`), each step also carries its own `id`/`state`.

So fixing `buildview` means reworking `build_watch.py`'s polling loop and
`build_display.py`'s tree rendering around `<build>/stages/tree`,
`<build>/stages/steps`, and `<build>/stages/log`, using `children` for
nesting and `state` for status, instead of `wfapi/describe` /
`stageFlowNodes` / `_links`.
