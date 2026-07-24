# Jenkins test environment for buildview

A disposable, local Jenkins instance for testing/developing `buildview`
against, pre-loaded with two pipeline jobs:

- `parallel-nested-demo` — nested and parallel stages (the main case for
  the stage-tree/console rendering).
- `simple-demo` — a plain 3-stage linear pipeline (Build/Test/Deploy). Its
  main purpose is just giving the job-browser's search list a second entry,
  since a couple of things (e.g. up/down navigation between list items) are
  awkward to test manually with only one job in the list.

## Usage

```shell
cd docker/jenkins-test
docker compose up -d --build
```

Wait ~10-20s for Jenkins to finish initializing, then:

- UI: http://localhost:8080 (user: `admin`, password: `admin`)
- Both jobs are created automatically via `init.groovy.d/seed-job.groovy`
  from the Jenkinsfiles in `pipelines/`.
- Auth for `buildview`/curl: HTTP basic auth with `admin` / `admin` works
  directly (CSRF protection is disabled via `JAVA_OPTS` for convenience, and
  the local security realm accepts the plain password over basic auth, so
  there's no need to mint a separate API token for this throwaway instance).

Trigger a build:

```shell
curl -u admin:admin -X POST 'http://localhost:8080/job/parallel-nested-demo/build?delay=0sec'
curl -u admin:admin -X POST 'http://localhost:8080/job/simple-demo/build?delay=0sec'
```

Point buildview at it directly:

```shell
echo 'USERNAME=admin
TOKEN=admin' > ../../.env
poetry run jenkins-buildview http://localhost:8080/job/parallel-nested-demo
```

Or run without arguments to land on the job browser (search box) against
this server, once you've logged in once via `poetry run jenkins-buildview`
and pointed it at `http://localhost:8080` with `admin`/`admin`.

Tear down:

```shell
docker compose down        # keep the named volume (jenkins_home)
docker compose down -v     # also delete it (full reset)
```

### Changing the seed script or Jenkinsfiles

The official Jenkins image only copies `init.groovy.d/` (and a few other
special directories) from the image into `$JENKINS_HOME` **once, if it
isn't already there** — so on an existing `jenkins_home` volume, rebuilding
the image after editing `init.groovy.d/seed-job.groovy` does *not* pick up
the change; the stale copy in the volume keeps running. Either:

```shell
docker compose down -v && docker compose up -d --build   # clean slate
```

or, to patch a running container without losing other state:

```shell
docker exec jenkins-test-jenkins-1 \
  cp /usr/share/jenkins/ref/init.groovy.d/seed-job.groovy /var/jenkins_home/init.groovy.d/seed-job.groovy
docker restart jenkins-test-jenkins-1
```

Jenkinsfiles under `pipelines/` aren't affected by this — the seed script
reads them straight from the image path (`/usr/share/jenkins/ref/pipelines/…`)
every time it runs, so editing those and rebuilding is enough on its own.

## Root cause of "the API no longer works" (fixed)

This environment is what the original `wfapi` → `stages` API migration
(now applied in `build_watch.py`/`build_display.py`) was diagnosed and
verified against. Kept here for reference. Confirmed against this
environment (Jenkins 2.541.3, current plugin versions as of 2026-07):
`buildview` used to be coded against the **old** `pipeline-stage-view`
plugin's `wfapi` REST API, which no longer ships at all —
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
