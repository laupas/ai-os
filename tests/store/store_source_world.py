import shutil
import subprocess
from pathlib import Path

HELLO_WORLD = Path(__file__).parents[2] / "examples" / "code-connectors" / "hello-world"

FILES = {
    "store.yaml": "name: Test templates\ndescription: For the tests.\n",
    "agents/cal.md": (
        "---\ndescription: Calendar.\nskills: [message-style]\n"
        "connectors: {gcal: null}\n"
        "store: {title: Calendar, category: Google, version: '1.0.0', author: Tester,\n"
        "  license: MIT, homepage: 'https://cal.example', tags: [google, calendar]}\n---\n\n"
        "You manage the calendar.\n"
    ),
    "agents/broken.md": "---\nmodel: sonnet\n---\n\nNo description.\n",
    "connectors/gcal.yaml": (
        "description: Google Calendar\n"
        "config: {type: http, url: 'https://cal.example/mcp', "
        "headers: {X-Client: '${GCAL_ID}', Authorization: 'Bearer ${GCAL_SECRET}'}}\n"
        "store:\n  notes: Make a client first.\n  variables:\n"
        "    - {variable: GCAL_ID, label: Client id, secret: false}\n"
        "    - {variable: GCAL_SECRET, label: Client secret}\n"
    ),
    "connectors/hello.yaml": "description: Hello\nconfig: {code: hello-world}\n",
    "triggers/brief.yaml": (
        "name: Morning brief\nprompt: Brief me.\ncron: ['0 7 * * 1-5']\n"
        "timezone: Europe/Zurich\nagent: cal\n"
    ),
}


def make_source(root: Path) -> str:
    """A store source as a git repository; returns its file:// URL."""
    for path, text in FILES.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    shutil.copytree(
        HELLO_WORLD, root / "code" / "hello-world", ignore=shutil.ignore_patterns("__pycache__")
    )
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "templates"], check=True)
    return root.as_uri()


def commit_change(root: Path, path: str, old: str, new: str) -> None:
    """Changes a file of the source and commits it, as its author would."""
    file = root / path
    file.write_text(file.read_text().replace(old, new))
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "commit", "-q", "-am", "change"], check=True)
