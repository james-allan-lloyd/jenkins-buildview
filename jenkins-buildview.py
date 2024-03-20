import httpx
import sys
import os
from icecream import ic
import subprocess
import time
import configparser
from os import path

def find_jobs(client: httpx.Client, jenkins_host: str, remotes: list[str]) -> list[str]:
    jobs = []
    for job in client.get(jenkins_host + "/api/json").json()["jobs"]:
        job_url = job["url"]
        job_data = client.get(job["url"] + "/api/json").json()
        if job_data["_class"] == "jenkins.branch.OrganizationFolder":
            ic(job_data)
            for org_job in job_data["jobs"]:
                org_job_data = client.get(org_job["url"]+"/api/json").json() 
                ic(org_job_data)

    return jobs


def get_branch_info_for_dir(d: str) -> tuple[list[str], str]:
    config = configparser.ConfigParser()
    config.read(path.join(d, ".git", "config"))
    remotes = []
    for section in config.sections():
        if section.startswith('remote'):
            remotes.append(config[section]["url"]) 

    with open(path.join(d, ".git", "HEAD")) as f:
        ref = f.read().partition(":")[-1].strip()

    return (remotes, ref)

def main():
    job_url = sys.argv[1]

    auth = (os.environ["USERNAME"], os.environ["TOKEN"])
    with httpx.Client(verify="/etc/ssl/certs/ca-bundle.crt", auth=auth) as client:
        while True:
            job_data = client.get(job_url + "/api/json").json()
            builds = sorted(job_data["builds"], key=lambda x: x["number"])
            latest_build = builds[-1]
            ic(latest_build)

            latest_build_data = client.get(latest_build["url"] + "/wfapi/describe").json()
            ic(latest_build_data)
            for stage in latest_build_data["stages"]:
                if 'error' in stage:
                    print(stage['name'], stage['status'], stage['error']['message'])
                else:
                    print(stage['name'], stage['status'])

            time.sleep(1)
            break



if __name__ == "__main__":
    main()
