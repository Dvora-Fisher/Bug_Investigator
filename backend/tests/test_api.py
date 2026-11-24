"""The HTTP API end to end: create -> pause (real interrupt) -> resume via the API -> report.
Uses the scripted reasoner and no Docker, so it is fast and free."""

from __future__ import annotations

import io
import threading
import time
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from investigator.api.app import create_app

from .test_graph import HYPOTHESES, fix, happy_script


@pytest.fixture
def make_client(make_service):
    def factory(reasoner) -> TestClient:
        return TestClient(create_app(make_service(reasoner)))
    return factory


def start(client: TestClient, **form) -> str:
    data = {"description": "moving_average returns one value too few", "source_type": "sample",
            "sample_id": "py-off-by-one", **form}
    r = client.post("/api/investigations", data=data)
    assert r.status_code == 202, r.text
    tid = r.json()["thread_id"]
    wait(client, tid)
    return tid


def wait(client: TestClient, tid: str) -> dict:
    client.app.state.manager.wait_until_idle(tid)
    return client.get(f"/api/investigations/{tid}").json()


def resume(client: TestClient, tid: str, body: dict, expect: int = 202) -> dict:
    r = client.post(f"/api/investigations/{tid}/resume", json=body)
    assert r.status_code == expect, r.text
    return wait(client, tid) if expect == 202 else r.json()


def test_pause_review_approve_and_report(make_client):
    client = make_client(happy_script())
    tid = start(client)

    view = client.get(f"/api/investigations/{tid}").json()
    assert view["status"] == "waiting_for_human"
    assert view["pending"]["type"] == "fix_review" and "window + 1" in view["pending"]["diff"]
    assert [h["id"] for h in view["hypotheses"]] == ["H1"] and view["evidence"][0]["id"] == "E1"

    events = client.get(f"/api/investigations/{tid}/events").text  # stream ends at the pause
    kinds = [line.split(": ", 1)[1] for line in events.splitlines() if line.startswith("event: ")]
    assert kinds[0] == "started" and kinds[-1] == "paused" and kinds.count("node") >= 6

    view = resume(client, tid, {"decision": "approve"})
    assert view["status"] == "done" and view["pending"] is None
    assert view["report"]["outcome"] == "fixed_unverified"
    assert client.get("/api/investigations").json()[0]["thread_id"] == tid


def test_reject_without_reason_asks_for_clarification(make_client):
    client = make_client(happy_script(propose_fix=[fix(), fix()]))
    tid = start(client)

    view = resume(client, tid, {"decision": "reject"})  # no feedback
    assert view["status"] == "waiting_for_human" and view["pending"]["type"] == "clarification"

    # an answer of the wrong shape is refused and nothing runs
    resume(client, tid, {"decision": "approve"}, expect=422)

    view = resume(client, tid, {"answer": "The bound should include the last window", "next_step": "revise_fix"})
    assert view["pending"]["type"] == "fix_review" and view["pending"]["attempt"] == 2
    assert view["review"]["feedback"] == "The bound should include the last window"


def test_resume_when_not_paused_is_a_conflict(make_client):
    client = make_client(happy_script())
    tid = start(client)
    resume(client, tid, {"decision": "approve"})
    assert "not waiting" in resume(client, tid, {"decision": "approve"}, expect=409)["detail"]


def test_events_can_be_replayed_after_a_sequence_number(make_client):
    client = make_client(happy_script())
    tid = start(client)
    lines = client.get(f"/api/investigations/{tid}/events?after=3").text.splitlines()
    first = json.loads(next(line for line in lines if line.startswith("data: "))[6:])
    assert first["seq"] == 4


@pytest.mark.parametrize("bad_id,code", [("not-a-thread", 422), ("0" * 32, 404), ("..%2F..%2Fsecrets", 404)])
def test_unknown_or_malformed_ids(make_client, bad_id, code):
    client = make_client(happy_script())
    assert client.get(f"/api/investigations/{bad_id}").status_code == code


def test_file_endpoint_stays_inside_the_workspace(make_client):
    client = make_client(happy_script())
    tid = start(client)
    assert "def moving_average" in client.get(f"/api/investigations/{tid}/file",
                                             params={"path": "stats/moving.py"}).text
    assert client.get(f"/api/investigations/{tid}/file", params={"path": "../meta.json"}).status_code == 404


def test_zip_upload_and_bad_sources(make_client):
    client = make_client(happy_script())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("proj/app.py", "def f():\n    return 1\n")
    r = client.post("/api/investigations", data={"description": "f returns wrong value", "source_type": "zip"},
                    files={"file": ("proj.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 202
    client.app.state.manager.wait_until_idle(r.json()["thread_id"])

    evil = io.BytesIO()
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../evil.py", "x")
    r = client.post("/api/investigations", data={"description": "zip slip attempt", "source_type": "zip"},
                    files={"file": ("e.zip", evil.getvalue(), "application/zip")})
    assert r.status_code == 400 and "Unsafe path" in r.json()["detail"]

    r = client.post("/api/investigations", data={"description": "bad repo url", "source_type": "github",
                                                 "github_url": "https://evil.example/x/y"})
    assert r.status_code == 400

    r = client.post("/api/investigations", data={"description": "unknown sample", "source_type": "sample",
                                                 "sample_id": "../../etc"})
    assert r.status_code == 400


def test_samples_and_health(make_client):
    client = make_client(happy_script())
    ids = {s["id"] for s in client.get("/api/samples").json()}
    assert {"py-off-by-one", "ts-null-reference", "cs-logic-error"} <= ids
    health = client.get("/api/health").json()
    assert health["monthly_budget_usd"] == 15 and health["docker"] is False


def test_evaluation_lists_saved_experiments_without_pilots(make_client):
    experiments = make_client(happy_script()).get("/api/evaluation").json()
    names = [e["name"] for e in experiments]
    assert "baseline-hard-927e30bd" in names and not any("pilot" in n for n in names)
    hard = next(e for e in experiments if e["name"] == "improved-hard-95a26917")
    assert hard["difficulty"] == "hard" and hard["summary"]["fix_success"] == 0.8 and len(hard["rows"]) == 5


def test_cancel_a_paused_investigation(make_client):
    client = make_client(happy_script())
    tid = start(client)  # pauses for the fix review
    r = client.post(f"/api/investigations/{tid}/cancel")
    assert r.status_code == 202 and r.json()["status"] == "cancelled"

    view = client.get(f"/api/investigations/{tid}").json()
    assert view["status"] == "cancelled" and view["pending"] is None and view["report"] is None
    resume(client, tid, {"decision": "approve"}, expect=409)  # a cancelled investigation cannot continue
    assert client.post(f"/api/investigations/{tid}/cancel").status_code == 409
    assert next(i for i in client.get("/api/investigations").json() if i["thread_id"] == tid)["status"] == "cancelled"


def test_cancel_a_running_investigation_stops_at_the_next_step(make_client):
    release = threading.Event()

    def slow_hypotheses(tools):
        release.wait(5)
        return HYPOTHESES

    reasoner = happy_script(generate_hypotheses=[slow_hypotheses])
    client = make_client(reasoner)
    r = client.post("/api/investigations", data={"description": "moving_average returns one value too few",
                                                 "source_type": "sample", "sample_id": "py-off-by-one"})
    tid = r.json()["thread_id"]
    deadline = time.monotonic() + 5
    while "generate_hypotheses" not in reasoner.calls and time.monotonic() < deadline:
        time.sleep(0.01)  # cancel while that step is in progress
    assert client.post(f"/api/investigations/{tid}/cancel").json()["status"] == "running"
    release.set()
    view = wait(client, tid)
    assert view["status"] == "cancelled" and view["report"] is None and view["proposed_fix"] is None
    nodes = [e["node"] for e in map(json.loads, (client.app.state.manager.service.settings.workspaces_dir / tid
                                                 / "events.jsonl").read_text().splitlines()) if e["kind"] == "node"]
    assert nodes[-1] == "generate_hypotheses", "no step may run after the one in progress"


def test_cancelled_workspace_starts_no_new_container(settings, tmp_path):
    from investigator.sandbox.docker_runner import DockerRunner

    runner = DockerRunner(settings)
    workspace = tmp_path / "ws"
    (workspace / "project").mkdir(parents=True)
    assert runner.kill_under(workspace) == 0
    result = runner.run("img", ["npm", "test"], workspace / "project", network=False, timeout_s=5)
    assert not result.ok and "cancelled" in result.output and result.seconds == 0
    runner.unblock(workspace)


def test_sandbox_progress_becomes_activity_events(make_client, tmp_path):
    client = make_client(happy_script())
    tid = start(client)
    manager = client.app.state.manager
    project = (manager.service.settings.workspaces_dir / tid / "project").resolve()
    manager._on_sandbox(project, {"phase": "start", "command": "npm ci", "network": True})
    manager._on_sandbox(tmp_path.resolve(), {"phase": "start", "command": "ignored"})  # not a workspace
    activity = [e for e in manager.events(tid).after(0) if e.kind == "activity"]
    assert [a.data["command"] for a in activity] == ["npm ci"]
    assert manager.status(tid) == "waiting_for_human", "activity events must not change the status"


def test_docker_runner_reports_start_and_end(settings, tmp_path, monkeypatch):
    import subprocess

    from investigator.sandbox import docker_runner

    monkeypatch.setattr(docker_runner.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="ok"))
    runner = docker_runner.DockerRunner(settings)
    seen = []
    runner.add_listener(lambda workdir, data: seen.append((workdir, data["phase"], data.get("exit_code"))))
    result = runner.run("img", ["npm", "test"], tmp_path, network=False, timeout_s=5)
    assert result.ok
    assert seen == [(tmp_path.resolve(), "start", None), (tmp_path.resolve(), "end", 0)]


def test_app_password_guards_every_api_route(make_service, settings):
    settings.app_password = "s3cret"
    settings.cors_origin_regex = r"https://.*\.onrender\.com"
    client = TestClient(create_app(make_service(happy_script())))
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/ping").json()["ok"] is True  # liveness check stays open
    assert client.get("/api/health", headers={"X-App-Password": "wrong"}).status_code == 401
    assert client.get("/api/health", headers={"X-App-Password": "s3cret"}).status_code == 200
    assert client.get("/api/samples?key=s3cret").status_code == 200  # server-sent events use ?key=
    # A preflight from the hosted frontend passes without the password, and a 401 still carries CORS headers.
    origin = "https://bug-investigator-web.onrender.com"
    pre = client.options("/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                                 "Access-Control-Request-Headers": "x-app-password"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == origin
    denied = client.get("/api/health", headers={"Origin": origin})
    assert denied.status_code == 401 and denied.headers["access-control-allow-origin"] == origin
