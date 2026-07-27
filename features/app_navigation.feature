Feature: Application entry points and global controls
  As a user
  I want a couple of ways to start buildview, and some always-available global keys
  So that I can point it directly at a job for scripting, or browse interactively

  Scenario: Direct-URL mode
    Given buildview is started with a job URL as a command-line argument
    Then it authenticates using USERNAME/TOKEN from the environment or a .env file
    And it goes straight to the build watch screen for that job
    And the job browser and login screen are never shown
    And there is no "back" out of the build watch screen

  Scenario: Interactive mode with valid saved credentials
    Given buildview is started with no command-line argument
    And valid credentials are already saved
    Then it goes straight to the job browser screen

  Scenario: Interactive mode with no valid saved credentials
    Given buildview is started with no command-line argument
    And there are no saved credentials, or they no longer work
    Then it shows the login screen

  Scenario: Toggling dark mode
    Given buildview is running, on any screen
    When I press "d"
    Then the app switches between dark and light mode

  Scenario: Quitting
    Given buildview is running, on any screen
    When I press "q"
    Then the application exits
