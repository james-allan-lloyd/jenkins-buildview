Feature: Logging in to a Jenkins server
  As a user with no saved credentials, or credentials that no longer work
  I want to enter my Jenkins server, username and API token
  So that buildview can authenticate me and remember me for next time

  Background:
    Given buildview was started with no job URL on the command line

  Scenario: First run, no saved credentials
    Given no credentials are stored for any server
    When the app starts
    Then I see the login screen
    And the server field is focused

  Scenario: Successful login
    Given I am on the login screen
    When I enter a server URL, username and API token
    And I submit the form
    Then buildview validates the credentials by calling "/whoAmI/api/json"
    And I am taken to the job browser screen
    And my credentials are saved for next time

  Scenario: Submitting the form
    Given I am on the login screen with all three fields filled in
    When I press Enter in any field, or click the "Login" button
    Then the same validation and login flow runs

  Scenario: Missing fields
    Given I am on the login screen
    When I submit the form with the server, username, or token left blank
    Then I see "Please fill in server, username and token"
    And I remain on the login screen

  Scenario: Invalid credentials or unreachable server
    Given I am on the login screen
    When I enter a server URL, username and API token
    And the server rejects them, or can't be reached
    Then I see "Login failed: invalid credentials or unreachable server"
    And I remain on the login screen

  Scenario: Returning with credentials that still work
    Given credentials were saved on a previous run
    And the saved server still accepts them
    When the app starts
    Then I skip the login screen entirely
    And I am taken directly to the job browser screen

  Scenario: Returning with credentials that no longer work
    Given credentials were saved on a previous run
    And the saved server now rejects them (e.g. a revoked token)
    When the app starts
    Then I see the login screen
