# TODO

- [x] BDD specs
- [x] for already completed builds, don't download each stage; instead just
      select the first.
- [ ] bugfix: hitting enter or space on a node should be ignored. It could in
      theory show all the logs for each subnode, provided it doesn't break our
      caching behaviour.
- [ ] tech debt: separate the built_watch tui from the async work in order to
      make it clear the flow.
- [ ] fix bug where no closing tag is found.
- [ ] feature change: back in direct url mode should still take you back to the
      job browser
- [ ] feature change: don't ask for API token, rather password - but store a
      token after calling a login endpoint
- [ ] feature change: don't show "ago" text until over a minute has elapsed.
      Just show "just now". This is to avoid unnecesary ticking
- [ ] improvement: need a way to search for a branch of a job (maybe adding a
      slash?)
