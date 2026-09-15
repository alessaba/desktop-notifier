from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from desktop_notifier import Notification
from desktop_notifier.backends import osc
from desktop_notifier.backends.osc import (
    OSCNotificationCenter,
    detect_protocol,
    format_notification,
)

ST = "\x1b\\"


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"TERM_PROGRAM": "ghostty", "TERM": "xterm-ghostty"}, "osc777"),
        ({"TERM_PROGRAM": "WezTerm"}, "osc777"),
        ({"TERM_PROGRAM": "WarpTerminal"}, "osc777"),
        ({"TERM_PROGRAM": "iTerm.app"}, "osc9"),
        ({"TERM_PROGRAM": "kitty"}, "osc9"),
        ({"TERM": "xterm-kitty"}, "osc9"),
        ({"TERM_PROGRAM": "Apple_Terminal"}, None),
        ({"TERM_PROGRAM": "vscode"}, None),
        ({"TERM": "dumb"}, None),
        ({}, None),
        # Notifications from multiplexers would need DCS passthrough.
        ({"TERM_PROGRAM": "ghostty", "TMUX": "/tmp/tmux-501/default,1,0"}, None),
        ({"TERM_PROGRAM": "ghostty", "STY": "1234.pts-0.host"}, None),
    ],
)
def test_detect_protocol(env: dict[str, str], expected: str | None) -> None:
    assert detect_protocol(env) == expected


def test_format_notification() -> None:
    assert (
        format_notification("osc9", "Title", "Message") == "\x1b]9;Title: Message" + ST
    )
    assert format_notification("osc9", "", "Message") == "\x1b]9;Message" + ST
    assert (
        format_notification("osc777", "Title", "Message")
        == "\x1b]777;notify;Title;Message" + ST
    )


def test_format_notification_sanitizes_text() -> None:
    assert (
        format_notification("osc777", "Ti\ntle", "\x1b[31mred\x1b[0m")
        == "\x1b]777;notify;Ti tle;red" + ST
    )


def test_format_notification_rejects_unknown_protocol() -> None:
    with pytest.raises(ValueError):
        format_notification("osc99", "Title", "Message")


@pytest.mark.asyncio
async def test_send_writes_escape_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[str] = []

    def fake_write(sequence: str) -> bool:
        written.append(sequence)
        return True

    monkeypatch.setattr(osc, "_write", fake_write)

    backend = OSCNotificationCenter("Test")
    backend.protocol = "osc9"
    await backend.send(Notification(title="Title", message="Message"))

    assert written == ["\x1b]9;Title: Message" + ST]
    assert len(await backend.get_current_notifications()) == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS backend selection")
def test_backend_selection_falls_back_to_terminal() -> None:
    from desktop_notifier import main
    from desktop_notifier.backends.dummy import DummyNotificationCenter

    bundle_patch = patch(
        "desktop_notifier.backends.macos_support.is_bundle", return_value=False
    )
    available_patch = patch(
        "desktop_notifier.backends.osc.is_available", return_value=True
    )
    with bundle_patch, available_patch:
        assert main.get_backend_class() is OSCNotificationCenter

    unavailable_patch = patch(
        "desktop_notifier.backends.osc.is_available", return_value=False
    )
    with bundle_patch, unavailable_patch:
        assert main.get_backend_class() is DummyNotificationCenter
