from datetime import datetime
from pathlib import Path

from telegram_listener import (
    build_message_output_path,
    load_listener_state,
    save_listener_state,
    save_messages_to_path,
)


def test_build_message_output_path_sanitizes_names(tmp_path):
    path = build_message_output_path(
        output_dir=tmp_path,
        folder_name="투자 채널/../",
        channel_name="삼성 리서치:*?",
        timestamp=datetime(2026, 5, 12, 9, 30, 5),
    )

    assert path == tmp_path / "투자채널" / "삼성리서치_20260512_093005.txt"


def test_save_messages_to_path_writes_content(tmp_path):
    filename = tmp_path / "group" / "channel_20260512_093005.txt"

    saved_path = save_messages_to_path(filename, ["첫 메시지", "둘째 메시지"])

    assert saved_path == filename
    assert filename.read_text(encoding="utf-8") == "첫 메시지\n\n둘째 메시지"


def test_save_messages_to_path_skips_empty_messages(tmp_path):
    filename = tmp_path / "group" / "channel_20260512_093005.txt"

    saved_path = save_messages_to_path(filename, [])

    assert saved_path is None
    assert not filename.exists()


def test_load_listener_state_returns_empty_when_missing(tmp_path):
    assert load_listener_state(tmp_path / "state.json") == {}


def test_save_and_load_listener_state(tmp_path):
    state_file = tmp_path / "state.json"

    saved_path = save_listener_state(state_file, {"123": 456})

    assert saved_path == state_file
    assert load_listener_state(state_file) == {"123": 456}


def test_load_listener_state_skips_invalid_file(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{not valid json", encoding="utf-8")

    assert load_listener_state(state_file) == {}
