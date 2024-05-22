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
