# Jenkins Build View

A text based Jenkins build tailer, built to watch pipelines.

## Requirements

Python 3.11 and a connection to PyPI. Also a Jenkins and associated token.

## Running

Make sure you have pipenv installed

```shell
pip install pipenv
```

Make sure everything installs and is available:

```shell
pipenv install
```

Generate a Jenkins user token, then add a file `.env` to the Root directory
with the following: 

```shell
USERNAME=<YOUR_JENKINS_USERNAME>
TOKEN=<YOUR_JENKINS_TOKEN>
```

Then you should be able to run it and follow the builds for a given job:

```shell
pipenv run python jenkins-buildview.py https://jenkins.example.com/job/organisation/job/pipeline-job/job/branch-name
```
