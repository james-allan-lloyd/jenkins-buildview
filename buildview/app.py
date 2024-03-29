import httpx
import sys
import os
import subprocess
import time
import configparser
from os import path
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree, RichLog
from textual.widget import Widget
from textual.reactive import reactive
from urllib.parse import urljoin
import json
import arrow

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
        log = RichLog(id="step_log", wrap=True)
        log.styles.display = "none"
        yield log

    def on_mount(self) -> None:
        self.set_interval(1, self.update_time_since_build, name="update-time-since-build-timer")

    def update_root_label(self, tree, build):
        if 'endTimeMillis' in build:
            status_time = arrow.get(build['endTimeMillis']).humanize(only_distance=True)  # startTimeMillis, durationMills
        elif 'startTimeMillis' in build:
            status_time = arrow.get(build['endTimeMillis']).humanize(only_distance=True)  # startTimeMillis, durationMills
        else:
            status_time = ''

        tree.root.label = f"Build {build['name']}: {build['status']} {status_time} ago"

    def update_time_since_build(self) -> None:
        if self.build is not None:
            tree = self.query_one("#build_tree", Tree)
            self.update_root_label(tree, self.build)


    def watch_build(self, old_build, new_build) -> None:
        tree = self.query_one("#build_tree", Tree)
        if new_build:
            self.update_root_label(tree, new_build)
            tree.root.remove_children()
            tree.root.expand()
            for stage in new_build["stages"]:
                label = f"{stage['name']} {stage['status']} {stage['error']['message'] if 'error' in stage else ''}"
                match stage['status']:
                    case 'SUCCESS': label = "[green]" + label
                    case 'FAILED': label = "[red]" + label
                    case 'IN_PROGRESS': label = "[white bold]" + label

                leaf = tree.root.add_leaf(label, stage)
        else:
            tree.root.label = "No build"
            



class JenkinsBuildViewApp(App):
    """An app to watch Jenkins builds"""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
                ("q", "quit", "Quit"),
                ("b", "build", "Build")]

    url = reactive("")
    latest_build_url = reactive("")
    current_stage_url: str | None = reactive(None)

    def __init__(self, initial_url=None):
        super().__init__()
        auth = (os.environ["USERNAME"], os.environ["TOKEN"])
        self.client =  httpx.Client(verify="/etc/ssl/certs/ca-bundle.crt", auth=auth)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Footer()
        display = BuildDisplay(id="build_display")
        display.client = self.client
        yield display

    async def on_mount(self) -> None:
        self.update_latest_build() 

    def on_tree_node_selected(self, message):
        if message.node.data is not None:
            log = self.query_one("#step_log")
            log.styles.display = "block"
            self.current_stage_url = urljoin(self.latest_build_url,  message.node.data["_links"]["self"]["href"])

    async def watch_current_stage_url(self, old, new):
        if new == None:
            log = self.query_one("#step_log")
            log.clear()
        else:
            self.get_logs(new)

    @work
    async def get_logs(self, url):
        data = self.client.get(url).json()
        if url == self.current_stage_url:
            log = self.query_one("#step_log")
            log.clear()

            for node in data["stageFlowNodes"]:
                log_data = self.client.get(urljoin(url, node["_links"]["log"]["href"])).json()
                if 'text' in log_data:
                    log.write(log_data['text'])

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    @work(exclusive=True)
    async def update_latest_build(self) -> None:
        job_data = self.client.get(self.url + "/api/json")
        try:
            job_data = job_data.json()
        except json.JSONDecodeError as e:
            raise Exception(f"Couldn't decode data: {job_data.content}")
        builds = sorted(job_data["builds"], key=lambda x: x["number"])
        self.latest_build_url = builds[-1]["url"]
        self.set_timer(3, self.update_latest_build, name="latest-build-update-timer")

    async def watch_latest_build_url(self, old_url, new_url):
        if len(new_url):
            self.update_build()

    @work(exclusive=True)
    async def update_build(self) -> None:
        build_display = self.query_one("#build_display", Static)

        latest_build_data = self.client.get(self.latest_build_url + "/wfapi/describe").json()
        build_display.build = latest_build_data
    
        if latest_build_data["status"] == "IN_PROGRESS" or latest_build_data["status"] == "NOT_EXECUTED":
            self.set_timer(2.5, self.update_build, name="build-update-timer")

    def action_quit(self) -> None:
        self.exit()

    async def action_build(self) -> None:
        self.client.post(self.url + "/build?delay=0sec")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    app = JenkinsBuildViewApp()
    app.url = sys.argv[1]
    app.run()

if __name__ == "__main__":
    main()
