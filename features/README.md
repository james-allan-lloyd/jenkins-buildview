# Behaviour overview

These `.feature` files are Gherkin documentation of buildview's behaviour,
written to be read, not executed — there are no step definitions and no
Cucumber/behave runner wired up. Treat them as a living spec/overview of what
the app does, organized by area:

- `login.feature` — first-run and repeat-run authentication
- `credential_storage.feature` — where/how the server, username and API
  token get persisted between runs
- `job_browser.feature` — searching and selecting a job
- `build_watch.feature` — the stage tree (pipeline view), auto-following the
  latest build, triggering builds
- `console_log_tailing.feature` — per-stage console log tailing, caching,
  and progressive rendering
- `app_navigation.feature` — direct-URL vs. interactive mode, global keys

Update these alongside behaviour changes the same way you'd update any other
doc — they're meant to stay accurate, not to rot as a historical snapshot.
