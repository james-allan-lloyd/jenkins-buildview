Feature: Storing login credentials
  As a user who has just logged in
  I want my server, username and API token remembered
  So that I don't have to log in every time I run buildview

  Scenario: Saving to the OS keychain (the common case)
    Given the OS has a working keychain / Secret Service provider
    When I log in successfully
    Then the server and username are saved to "~/.config/jenkins-buildview/config.json"
    And the API token is saved to the OS keychain, not written to disk in plain text

  Scenario: Falling back when no OS keychain is available
    Given the OS has no keychain / Secret Service provider (e.g. a headless Linux server)
    When I log in successfully
    Then the server and username are still saved to the config file
    And the API token is saved to a fallback file next to the config file
    And that fallback file is readable and writable only by my own user
    And I see a warning notification explaining credentials were saved without a keychain

  Scenario: Credential storage fails entirely
    Given both the keychain and the fallback file write fail
    When I log in successfully
    Then I see a warning that I'll need to log in again next time
    But I am still taken to the job browser for this session

  Scenario: Loading previously stored credentials
    Given a config file with a server and username exists
    And a token is retrievable from the keychain, or otherwise from the fallback file
    When the app starts
    Then those credentials are loaded and used to build the authenticated client

  Scenario: A missing or corrupted config file is treated as "no credentials"
    Given the config file is missing, unreadable, not valid JSON, or missing server/username
    When the app starts
    Then buildview behaves as if no credentials were ever saved
    And I see the login screen

  Scenario: A saved account with no retrievable token
    Given the config file names a server and username
    But no token can be found in either the keychain or the fallback file
    When the app starts
    Then buildview behaves as if no credentials were ever saved
    And I see the login screen
