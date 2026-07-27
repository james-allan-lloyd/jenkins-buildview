Feature: Following build console output stage by stage
  As a user watching a running build
  I want the console to show one stage's log at a time, tailing the active
  stage live
  So that I can see what's happening right now without scrolling through the
  entire build's combined output, and switching between stages is instant

  Background:
    Given I am on the build watch screen with a build in progress

  Scenario: The console follows the currently active stage by default
    Given a new leaf stage starts running
    Then the console is cleared
    And the console's title is set to that stage's name
    And console content is only ever that one stage's log, never the whole build's history concatenated together

  Scenario: Live tailing an active stage
    Given the console is currently showing the active stage
    When more console output becomes available on the server
    Then only the new text is appended to the console
    And the cached copy of that stage's log grows to match

  Scenario: Caching a stage's log once downloaded
    Given a stage's log has already been fetched, fully or partially
    When buildview polls that stage's log again
    Then only the text beyond what's already cached is treated as new
    And nothing already shown is re-rendered or re-appended

  Scenario: Viewing a finished stage's log
    Given an earlier stage has already finished
    When I select that stage in the tree
    Then the console clears and shows that stage's log from cache, instantly, with no network request needed
    And the console stops auto-following the currently active stage

  Scenario: Returning to the live stage
    Given I am viewing a finished stage's cached log
    And a different stage is currently active
    When I select the currently active stage in the tree
    Then the console resumes live tailing of that stage
    And auto-follow is re-enabled, so the console will follow future stages too

  # The underlying Jenkins API has no byte-offset/range parameter, so every
  # poll still re-downloads the full log over the wire -- streaming avoids
  # buffering it all into memory at once and avoids one huge blocking write
  # to the console, but doesn't reduce total bytes transferred.
  Scenario: Progressive rendering of a large log
    Given a stage's console log is large
    When buildview fetches it
    Then the response is streamed and rendered into the console incrementally, chunk by chunk, as it downloads
    And the UI is not blocked waiting for the entire log body before showing anything

  Scenario: A new build resets all caches
    Given buildview switches to following a new build
    Then all previously cached stage logs are discarded
    And the console is cleared and its title reset to the default
    And stage-following resets, so the new build's first stage is tailed live
