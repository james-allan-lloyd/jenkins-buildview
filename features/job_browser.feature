Feature: Browsing and selecting a Jenkins job
  As a logged-in user
  I want to search across all jobs on the server, including ones nested in
  folders and multibranch pipelines
  So that I can quickly find and start following the one I care about

  Background:
    Given I am on the job browser screen

  Scenario: Jobs load on entry
    When the screen mounts
    Then I see "Loading jobs..."
    And the full job list is fetched recursively, flattening folders and multibranch pipelines into a single list
    And each job is shown as "<folder> » <folder> » <job name>"

  Scenario: No jobs found
    Given the server has no buildable jobs
    When the job list finishes loading
    Then I see "No jobs found"

  Scenario: Job list fails to load
    Given the request to list jobs fails
    Then I see an error message containing the failure reason

  Scenario: Filtering jobs by search text
    Given the full job list has loaded
    When I type into the search box
    Then only jobs whose path contains the search text, case-insensitively, remain listed

  Scenario: Clearing the search box shows everything again
    Given the list is currently filtered
    When I clear the search box
    Then the full job list is shown again

  Scenario: Down arrow from the search box jumps into the list
    Given my cursor is in the search box
    And the job list has at least one entry
    When I press Down
    Then the first item in the job list is highlighted
    And keyboard focus moves to the job list
    But no job is opened yet

  Scenario: Enter in the search box behaves the same as Down
    Given my cursor is in the search box
    When I press Enter
    Then the first item in the job list is highlighted and focused
    But no job is opened yet -- a second, explicit selection is required

  Scenario: Up arrow at the top of the list returns to search
    Given focus is on the job list
    And the first item (index 0) is highlighted
    When I press Up
    Then focus returns to the search box
    And the list highlight does not wrap around to the last item

  Scenario: Up arrow elsewhere in the list behaves normally
    Given focus is on the job list
    And the highlighted item is not the first one
    When I press Up
    Then the highlight simply moves to the previous item, as usual

  Scenario: Selecting a job opens it
    Given a job is highlighted in the list
    When I press Enter, or click the job
    Then I am taken to the build watch screen for that job
