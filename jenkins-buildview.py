import httpx
import sys
import os
from icecream import ic
import subprocess
import time
import configparser
from os import path
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree
from textual.widget import Widget
from textual.reactive import reactive

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





class BuildDisplay(Static):

    build: dict | None = reactive(None)    

    def compose(self) -> ComposeResult:
        yield Tree(id="build_tree", label="No build")

    def watch_build(self, old_build, new_build) -> None:
        tree = self.query_one("#build_tree", Tree)
        tree.root.label = new_build["name"] if new_build is not None else "No build"
        if new_build:
            tree.root.remove_children()
            tree.root.expand()
            for stage in new_build["stages"]:
                label = f"{stage['name']} {stage['status']} {stage['error']['message'] if 'error' in stage else ''}"
                match stage['status']:
                    case 'SUCCESS': label = "[green]" + label
                    case 'FAILED': label = "[red]" + label

                leaf = tree.root.add_leaf(label)
            # for stage in new_build["stages"]:
            #    if 'error' in stage:
            #        print(stage['name'], stage['status'], stage['error']['message'])
            #    else:
            #        print(stage['name'], stage['status'])



class JenkinsBuildViewApp(App):
    """An app to watch Jenkins builds"""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
                ("q", "quit", "Quit"),
                ("r", "refresh", "Refresh")]

    url = reactive("")
    latest_build_url = reactive("")

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Footer()
        yield BuildDisplay(id="build_display")

    def on_mount(self) -> None:
        self.set_interval(5, self.update_latest_build)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    @work(exclusive=True)
    async def update_latest_build(self) -> None:
        auth = (os.environ["USERNAME"], os.environ["TOKEN"])
        with httpx.Client(verify="/etc/ssl/certs/ca-bundle.crt", auth=auth) as client:
            job_data = client.get(self.url + "/api/json").json()
            builds = sorted(job_data["builds"], key=lambda x: x["number"])
            self.latest_build_url = builds[-1]["url"]

    async def watch_latest_build_url(self, old_url, new_url):
        self.update_build()

    @work(exclusive=True)
    async def update_build(self) -> None:
        build_display = self.query_one("#build_display", Static)
        
        # Query the network API
        auth = (os.environ["USERNAME"], os.environ["TOKEN"])
        with httpx.Client(verify="/etc/ssl/certs/ca-bundle.crt", auth=auth) as client:
            job_data = client.get(self.url + "/api/json").json()
            builds = sorted(job_data["builds"], key=lambda x: x["number"])
            latest_build = builds[-1]
            latest_build_data = client.get(latest_build["url"] + "/wfapi/describe").json()

            build_display.build = latest_build_data
            print(latest_build_data["status"])
        
            if latest_build_data["status"] == "IN_PROGRESS":
                self.set_timer(2.5, self.update_build, name="build-update-timer")

    def action_quit(self) -> None:
        self.exit()

    async def action_refresh(self) -> None:
        self.update_build(self.url)


if __name__ == "__main__":
    app = JenkinsBuildViewApp()
    app.url = sys.argv[1]
    app.run()
