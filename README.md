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

Generate a Jenkins user token, then add a file `.env` to the Root directory
with the following:

```shell
USERNAME=<YOUR_JENKINS_USERNAME>
TOKEN=<YOUR_JENKINS_TOKEN>
```

Then you should be able to run it and follow the builds for a given job:

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
poetry run textual run --dev buildview.app <BUILD_URL>
```

You should then be able to see what's printed.
