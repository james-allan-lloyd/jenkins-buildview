from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from buildview.auth import Credentials, build_http_client, validate


class LoginScreen(Screen):
    """Prompts for Jenkins server, username and API token, validates them,
    then hands the client off to the app."""

    BINDINGS = [("enter", "submit", "Login")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Jenkins Login", id="login_title"),
            Label("", id="login_error"),
            Input(placeholder="https://jenkins.example.com", id="server_input"),
            Input(placeholder="username", id="username_input"),
            Input(placeholder="API token", password=True, id="token_input"),
            Button("Login", id="login_button", variant="primary"),
            id="login_form",
        )

    def on_mount(self) -> None:
        self.query_one("#server_input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login_button":
            self.action_submit()

    @work(exclusive=True)
    async def action_submit(self) -> None:
        server = self.query_one("#server_input", Input).value.strip().rstrip("/")
        username = self.query_one("#username_input", Input).value.strip()
        token = self.query_one("#token_input", Input).value.strip()
        error_label = self.query_one("#login_error", Label)

        if not server or not username or not token:
            error_label.update("Please fill in server, username and token")
            return

        error_label.update("Checking credentials...")
        client = build_http_client(server, username, token)
        if await validate(client):
            self.app.handle_login(Credentials(server=server, username=username, token=token), client)
        else:
            await client.aclose()
            error_label.update("Login failed: invalid credentials or unreachable server")
