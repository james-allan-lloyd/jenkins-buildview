Feature: Watching a job's pipeline build
  As a user following a Jenkins job
  I want to see its stage structure and always be looking at the most recent build
  So that I don't have to manually refresh or hunt for the latest run

  Background:
    Given I am on the build watch screen for a job

  Scenario: A job that has never been built
    Given the job has no builds yet
    Then the stage tree shows "Not built yet - press B to build"
    And no stage or console content is shown
    And no crash occurs

  Scenario: Triggering a build
    Given I am on the build watch screen
    When I press "b"
    Then a build is triggered via a POST to the job's build endpoint

  Scenario: Automatically following the latest build
    Given the job's "last build" changes to a new build
    Then buildview switches to following that new build automatically
    And the stage tree and console reset for the new build

  Scenario: Rendering nested and parallel stages
    Given a build has nested and/or parallel stages
    Then the stage tree mirrors that structure exactly, including nested children
    And each stage node shows its name and current state

  Scenario Outline: Stage coloring by state
    Given a stage is in state "<state>"
    Then it is rendered in "<style>"

    Examples:
      | state    | style      |
      | queued   | white bold |
      | running  | white bold |
      | paused   | white bold |
      | success  | green      |
      | unstable | yellow     |
      | failure  | red        |
      | aborted  | red        |

  Scenario: Root label while a build is running
    Given the current build is still in progress
    Then the root of the tree shows "Build <name>: <status> <time since it started> ago"
    And that "ago" time keeps updating live, once a second

  Scenario: Root label once a build finishes
    Given the current build has completed
    Then the root of the tree shows "Build <name>: <status> <time since it ended> ago"

  Scenario: Showing changesets
    Given the current build has associated SCM changes
    Then the root label is suffixed with "(changes: <comma-separated commit summaries>)"

  Scenario: Selecting a stage in the tree
    Given the stage tree is populated
    When I select a stage node
    Then the console pane shows that stage's log (see console_log_tailing.feature)

  Scenario: Going back to the job browser
    Given I opened this screen from the job browser
    When I press Escape
    Then I return to the job browser screen

  Scenario: No "back" in direct-URL mode
    Given buildview was started with a job URL on the command line
    When I press Escape
    Then nothing happens -- there is no job browser to go back to
