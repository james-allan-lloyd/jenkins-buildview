# Jenkins Build View

A text based Jenkins build tailer, built to watch pipelines.

## Requirements

Python 3.11 and a connection to PyPI. Also a Jenkins and associated token.

## Running

Make sure you have poetry installed

```shell
pip install poetry
```

Make sure everything installs and is available:

```shell
poetry install
```

Generate a Jenkins user token, then run the app with no arguments:

```shell
poetry run jenkins-buildview
```

On first run you'll be prompted to log in with your Jenkins server URL,
username, and API token. The token is validated against the server and then
stored securely in your OS keychain (via `keyring`); the server URL and
username are cached in `~/.config/jenkins-buildview/config.json`. On
subsequent runs, if the stored token is still valid you'll skip straight to
a searchable list of jobs on that server &mdash; type to filter, then select
a job (or press enter) to start following its builds. Press `escape` while
watching a build to go back to the job list.

### Direct URL mode

You can still jump straight to tailing a specific job, bypassing the login
and browsing screens, by passing its URL as an argument and providing
credentials via a `.env` file in the root directory:

```shell
USERNAME=<YOUR_JENKINS_USERNAME>
TOKEN=<YOUR_JENKINS_TOKEN>
```

```shell
poetry run jenkins-buildview https://jenkins.example.com/job/organisation/job/pipeline-job/job/branch-name
```

## Debugging

Because this program uses textual for its display and takes over the screen,
getting output to aid in debugging can be difficult. Textual provides a
"console" application that allows you to see what's going on with the
application.

Start the console like this:

```shell
poetry run textual console -x SYSTEM -x EVENT -x DEBUG \
  -x WORKER  # remove if you want to see framework events too
```

And then start the application like this:

```shell
poetry run textual run --dev buildview.app
```

To jump straight to tailing a specific job instead of the login/browse
screens (see [Direct URL mode](#direct-url-mode)), pass its URL as an
argument:

```shell
poetry run textual run --dev buildview.app <BUILD_URL>
```

You should then be able to see what's printed.
