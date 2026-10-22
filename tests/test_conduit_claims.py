"""The dashboard lets go of Conduit's claim on a chat once it sits idle, so
Hermes Desktop can open it again (hermes-conduit#1123)."""
import importlib
import pathlib
import sys
import threading
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if "conduit_push" not in sys.modules:
    _pkg = types.ModuleType("conduit_push")
    _pkg.__path__ = [str(ROOT)]
    sys.modules["conduit_push"] = _pkg

claims = importlib.import_module("conduit_push.conduit_claims")

NOW = 10_000.0
IDLE = NOW - claims.IDLE_S - 1
DETACHED = object()


class Lease:
    def __init__(self, enabled=True):
        self.session_id = "stored-1"
        self.enabled = enabled
        self.released = False


class Socket:
    def __init__(self, headers):
        self.headers = headers


class WSTransport:
    """Hermes' socket transport: the upgrade's headers on ``_ws``, ``_closed``."""

    def __init__(self, headers, closed=False):
        self._ws = Socket(headers)
        self._closed = closed


class FanoutTransport:
    def __init__(self, *peers):
        self.peers = list(peers)

    def transports(self):
        return list(self.peers)


class JobTransport:
    conduit_client = "conduit"


def conduit(closed=False):
    return WSTransport({"X-Conduit-Client": "conduit", "User-Agent": "Conduit/2.0"}, closed=closed)


def desktop(closed=False):
    return WSTransport({"User-Agent": "Mozilla/5.0 Electron/38"}, closed=closed)


class Server:
    def __init__(self):
        self._sessions = {}
        self._sessions_lock = threading.Lock()
        self._detached_ws_transport = DETACHED
        self.pending = {}
        self.delegating = set()
        self.released = []

    def _session_pending_kind(self, sid):
        return self.pending.get(sid, "")

    def _session_has_active_delegations(self, sid, session=None):
        return sid in self.delegating

    def _release_active_session_slot(self, session):
        lease = session.get("active_session_lease")
        lease.released = True
        session.pop("active_session_lease")
        self.released.append(lease.session_id)
        return True


def chat(server, sid="live-1", transport=None, **fields):
    ready = threading.Event()
    ready.set()
    session = {"active_session_lease": Lease(), "running": False, "last_active": IDLE, "agent_ready": ready,
               "history_lock": threading.Lock(), "session_key": "stored-1", "source": "desktop",
               "transport": conduit() if transport is None else transport, **fields}
    server._sessions[sid] = session
    return session


def sweep(server, now=NOW):
    return claims.sweep(server, lambda: ROOT, now=now)


@pytest.fixture(autouse=True)
def no_turn_markers(monkeypatch):
    monkeypatch.delitem(sys.modules, "tui_gateway.turn_marker", raising=False)


def test_an_idle_conduit_chat_lets_go_of_its_claim():
    server = Server()
    session = chat(server)
    assert sweep(server) == 1
    assert server.released == ["stored-1"]
    assert "active_session_lease" not in session
    assert sweep(server) == 0  # nothing left to let go


def test_a_chat_used_within_the_last_minute_keeps_it():
    server = Server()
    chat(server, last_active=NOW - claims.IDLE_S + 5)
    assert sweep(server) == 0


@pytest.mark.parametrize("fields", [
    {"running": True},
    {"_closing": True},
    {"follow_profile_config": True},  # Bot Chat
    {"room_plumbing": True},
    {"source": "bot_room"},
    {"active_session_lease": Lease(enabled=False)},  # an isolated child's borrowed token
    {"active_session_lease": None},
])
def test_chats_that_keep_their_claim(fields):
    server = Server()
    chat(server, **fields)
    assert sweep(server) == 0


def test_a_chat_still_building_keeps_it():
    server = Server()
    chat(server, agent_ready=threading.Event())
    assert sweep(server) == 0


def test_waiting_on_an_answer_or_delegated_work_keeps_it():
    server = Server()
    chat(server, sid="asking")
    chat(server, sid="delegating")
    server.pending["asking"] = "clarify.request"
    server.delegating.add("delegating")
    assert sweep(server) == 0


def test_a_chat_desktop_has_open_in_this_process_keeps_it():
    server = Server()
    chat(server, sid="desktop", transport=desktop())
    chat(server, sid="both", transport=FanoutTransport(conduit(), desktop()))
    assert sweep(server) == 0


def test_a_viewer_that_left_does_not_count():
    server = Server()
    chat(server, transport=FanoutTransport(conduit(), desktop(closed=True)))
    assert sweep(server) == 1


def test_the_plugins_own_jobs_count_as_conduit():
    server = Server()
    chat(server, transport=JobTransport())
    assert sweep(server) == 1


def test_a_chat_conduit_left_counts_once_seen_with_conduit():
    server = Server()
    session = chat(server, last_active=NOW)
    assert sweep(server) == 0  # still in use, but now known to be Conduit's
    session["transport"] = DETACHED
    assert sweep(server, now=NOW + claims.IDLE_S + 1) == 1


def test_a_parked_chat_never_seen_with_conduit_keeps_it():
    server = Server()
    chat(server, transport=DETACHED)
    assert sweep(server) == 0


def test_desktop_joining_clears_the_mark():
    server = Server()
    session = chat(server, last_active=NOW)
    sweep(server)
    session["transport"] = desktop()
    sweep(server)
    session["transport"] = DETACHED
    assert sweep(server, now=NOW + claims.IDLE_S + 1) == 0


def test_a_stdio_tui_keeps_it():
    server = Server()
    chat(server, transport=object())
    assert sweep(server) == 0


def test_a_turn_marker_keeps_it(monkeypatch):
    marker = types.ModuleType("tui_gateway.turn_marker")
    marker.read_turn_marker = lambda home, key: {"writer_pid": 4321} if key == "stored-1" else None
    marker.marker_writer_state = lambda entry: "alive"
    monkeypatch.setitem(sys.modules, "tui_gateway.turn_marker", marker)
    server = Server()
    chat(server)
    assert sweep(server) == 0
    marker.marker_writer_state = lambda entry: "dead"  # a crash leftover, not a turn
    assert sweep(server) == 1


def test_an_unreadable_turn_marker_keeps_it(monkeypatch):
    marker = types.ModuleType("tui_gateway.turn_marker")

    def unreadable(home, key):
        raise OSError("disk")

    marker.read_turn_marker = unreadable
    marker.marker_writer_state = lambda entry: "dead"
    monkeypatch.setitem(sys.modules, "tui_gateway.turn_marker", marker)
    server = Server()
    chat(server)
    assert sweep(server) == 0


def test_a_turn_admitted_during_the_check_keeps_it():
    server = Server()
    session = chat(server)
    assert claims.releasable(server, "live-1", session, NOW, lambda: ROOT)
    session["running"] = True  # admission marks it under the same lock
    assert not claims.release(server, "live-1", session, NOW)
    assert server.released == []


def test_a_hermes_without_the_helpers_lets_nothing_go():
    server = Server()
    chat(server)
    server._session_pending_kind = None
    assert sweep(server) == 0
    assert sweep(None) == 0


def test_one_odd_runtime_never_stops_the_pass():
    server = Server()
    chat(server, sid="odd")
    server._sessions["odd"]["history_lock"] = "not a lock"
    chat(server, sid="fine")
    assert sweep(server) == 1
