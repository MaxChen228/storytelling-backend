#!/usr/bin/env python3
"""Play an audio file while printing synchronized SRT subtitles to the terminal."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import selectors
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:  # pragma: no cover - Windows-only dependency
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - POSIX path
    msvcrt = None


@dataclass
class SubtitleLine:
    index: int
    start: float
    end: float
    text: str


@dataclass
class PlayerChoice:
    command: List[str]
    name: str
    supports_seek: bool = False


SEEK_STEP_SECONDS = 15
IPC_READY_TIMEOUT = 3.0
TIME_REWIND_THRESHOLD = 0.4


class SubtitleRenderer:
    """Render subtitles based on the external playback clock."""

    def __init__(self, subtitles: List[SubtitleLine], limit: Optional[int] = None) -> None:
        self._subtitles = subtitles
        self._limit = len(subtitles) if limit is None else min(limit, len(subtitles))
        self._next_index = 0
        self._last_time = 0.0
        self._finished = self._limit == 0

    @property
    def finished(self) -> bool:
        return self._finished

    def _recalculate_index(self, current_time: float) -> None:
        target = 0
        while target < self._limit and self._subtitles[target].start < current_time:
            target += 1
        if target != self._next_index:
            print()
            print(f"⏪ 跳至 {format_timestamp(max(current_time, 0.0))}")
        self._next_index = target

    def update(self, current_time: float) -> None:
        if self._finished:
            return
        if current_time + TIME_REWIND_THRESHOLD < self._last_time:
            self._recalculate_index(current_time)
        while self._next_index < self._limit and self._subtitles[self._next_index].start <= current_time:
            subtitle = self._subtitles[self._next_index]
            timestamp = format_timestamp(subtitle.start)
            duration = subtitle.end - subtitle.start
            print(f"\r[{timestamp} / +{duration:4.1f}s] {subtitle.text}      ")
            self._next_index += 1
        self._last_time = current_time
        if self._next_index >= self._limit:
            self._finished = True


class KeyListener:
    """Cross-platform, non-blocking keyboard listener for arrow keys."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled and sys.stdin.isatty()
        self._selector: Optional[selectors.BaseSelector] = None
        self._fd: Optional[int] = None
        self._old_settings = None
        self._old_flags = None
        self._closed = False
        self._buffer: str = ""

    def __enter__(self) -> "KeyListener":
        if not self.enabled:
            return self
        if os.name == "nt":
            return self
        import termios  # pragma: no cover - POSIX specific
        import tty  # pragma: no cover - POSIX specific
        import fcntl  # pragma: no cover - POSIX specific

        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._old_flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
        fcntl.fcntl(self._fd, fcntl.F_SETFL, self._old_flags | os.O_NONBLOCK)
        self._selector = selectors.DefaultSelector()
        self._selector.register(sys.stdin, selectors.EVENT_READ)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.enabled and os.name != "nt" and self._fd is not None and self._old_settings is not None:
            import termios  # pragma: no cover - POSIX specific
            import fcntl  # pragma: no cover - POSIX specific

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            if self._old_flags is not None:
                fcntl.fcntl(self._fd, fcntl.F_SETFL, self._old_flags)
        if self._selector:
            with contextlib.suppress(Exception):
                self._selector.unregister(sys.stdin)
            self._selector.close()
            self._selector = None

    def poll_key(self, timeout: float) -> Optional[str]:
        if not self.enabled:
            if timeout > 0:
                time.sleep(timeout)
            return None
        if os.name == "nt":
            if not msvcrt:  # pragma: no cover - sanity guard
                time.sleep(timeout)
                return None
            end_time = time.perf_counter() + timeout
            while time.perf_counter() < end_time:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in {"\x00", "\xe0"}:  # special key prefix
                        code = msvcrt.getwch()
                        if code == "M":
                            return "RIGHT"
                        if code == "K":
                            return "LEFT"
                    elif ch == " ":
                        return "SPACE"
                    elif ch == "\x03":
                        raise KeyboardInterrupt
                time.sleep(0.01)
            return None
        if not self._selector or self._fd is None:
            time.sleep(timeout)
            return None
        events = self._selector.select(timeout)
        if not events:
            return None
        try:
            chunk = os.read(self._fd, 32)
        except BlockingIOError:
            return None
        if not chunk:
            return None
        self._buffer += chunk.decode(errors="ignore")
        while self._buffer:
            ch = self._buffer[0]
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == " ":
                self._buffer = self._buffer[1:]
                return "SPACE"
            if ch != "\x1b":
                self._buffer = self._buffer[1:]
                continue
            if len(self._buffer) < 3:
                return None
            sequence = self._buffer[:3]
            self._buffer = self._buffer[3:]
            if sequence == "\x1b[C":
                return "RIGHT"
            if sequence == "\x1b[D":
                return "LEFT"
        return None


class MPVController:
    """Control mpv via its IPC socket to enable seeking and time tracking."""

    def __init__(self, audio_path: Path, base_command: List[str]) -> None:
        if os.name != "posix":
            raise RuntimeError("mpv 快轉功能目前只支援 POSIX 系統")
        self.audio_path = audio_path
        self.base_command = list(base_command)
        self.process: Optional[subprocess.Popen] = None
        self._socket: Optional[socket.socket] = None
        self._reader: Optional[threading.Thread] = None
        self._writer = None
        self._reader_file = None
        self._write_lock = threading.Lock()
        self._stop_reader = threading.Event()
        self._time_pos = 0.0
        self._time_lock = threading.Lock()
        self._paused = False
        self._state_lock = threading.Lock()
        self._ipc_path: Optional[Path] = None
        self._cleanup_dir: Optional[Path] = None

    def _ensure_command_flags(self, cmd: List[str]) -> None:
        def has_flag(flag: str) -> bool:
            return any(arg == flag or arg.startswith(f"{flag}=") for arg in cmd)

        if not has_flag("--no-video"):
            cmd.append("--no-video")
        if not has_flag("--force-window"):
            cmd.append("--force-window=no")
        if not has_flag("--keep-open"):
            cmd.append("--keep-open=no")
        if not has_flag("--input-terminal"):
            cmd.append("--input-terminal=no")
        if not has_flag("--really-quiet"):
            cmd.append("--really-quiet")

    def _extract_ipc_path(self, cmd: List[str]) -> Optional[str]:
        for idx, arg in enumerate(cmd):
            if arg == "--input-ipc-server" and idx + 1 < len(cmd):
                return cmd[idx + 1]
            if arg.startswith("--input-ipc-server="):
                return arg.split("=", 1)[1]
        return None

    def start(self) -> None:
        cmd = list(self.base_command)
        self._ensure_command_flags(cmd)
        ipc_path = self._extract_ipc_path(cmd)
        if ipc_path:
            self._ipc_path = Path(ipc_path)
        else:
            base_tmp = Path("/tmp") if os.name == "posix" and Path("/tmp").exists() else Path(tempfile.gettempdir())
            tmpdir = Path(tempfile.mkdtemp(prefix="mpv-ipc-", dir=str(base_tmp)))
            self._cleanup_dir = tmpdir
            self._ipc_path = tmpdir / "socket"
            cmd.append(f"--input-ipc-server={self._ipc_path}")
        cmd.append(str(self.audio_path))
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + IPC_READY_TIMEOUT
        while time.time() < deadline:
            if self._ipc_path and self._ipc_path.exists():
                break
            if self.process.poll() is not None:
                raise RuntimeError("mpv 無法啟動：請檢查指令是否正確")
            time.sleep(0.05)
        else:
            raise RuntimeError("mpv IPC 初始化逾時")
        assert self._ipc_path is not None
        self._socket = socket.socket(socket.AF_UNIX)
        self._socket.connect(str(self._ipc_path))
        self._reader_file = self._socket.makefile("r", encoding="utf-8")
        self._writer = self._socket.makefile("w", encoding="utf-8")
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        self._send({"command": ["observe_property", 1, "time-pos"]})
        self._send({"command": ["observe_property", 2, "pause"]})

    def _reader_loop(self) -> None:
        if not self._reader_file:
            return
        while not self._stop_reader.is_set():
            line = self._reader_file.readline()
            if not line:
                break
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(line)
                if data.get("event") == "property-change" and data.get("name") == "time-pos":
                    value = data.get("data")
                    if isinstance(value, (int, float)):
                        with self._time_lock:
                            self._time_pos = float(value)
                elif data.get("event") == "property-change" and data.get("name") == "pause":
                    value = data.get("data")
                    if isinstance(value, bool):
                        with self._state_lock:
                            self._paused = value
        self._stop_reader.set()

    def _send(self, payload: Dict[str, object]) -> None:
        if not self._writer:
            return
        with self._write_lock:
            self._writer.write(json.dumps(payload))
            self._writer.write("\n")
            self._writer.flush()

    def current_time(self) -> float:
        with self._time_lock:
            return self._time_pos

    def seek(self, seconds: float) -> None:
        self._send({"command": ["seek", seconds, "relative"]})

    def toggle_pause(self) -> bool:
        with self._state_lock:
            new_state = not self._paused
            self._paused = new_state
        self._send({"command": ["set_property", "pause", new_state]})
        return new_state

    def is_paused(self) -> bool:
        with self._state_lock:
            return self._paused

    def poll(self) -> Optional[int]:
        if not self.process:
            return None
        return self.process.poll()

    def wait(self) -> None:
        if self.process:
            self.process.wait()

    def terminate(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def close(self) -> None:
        self._stop_reader.set()
        if self._writer:
            with contextlib.suppress(Exception):
                self._writer.close()
            self._writer = None
        if self._reader_file:
            with contextlib.suppress(Exception):
                self._reader_file.close()
            self._reader_file = None
        if self._socket:
            with contextlib.suppress(Exception):
                self._socket.close()
            self._socket = None
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=0.1)
        if self._cleanup_dir and self._ipc_path:
            with contextlib.suppress(FileNotFoundError):
                self._ipc_path.unlink()
            with contextlib.suppress(OSError):
                self._cleanup_dir.rmdir()



def parse_srt(srt_path: Path) -> List[SubtitleLine]:
    """Parse an SRT file into structured subtitle lines."""
    raw = srt_path.read_text(encoding="utf-8").strip()
    blocks = raw.split("\n\n")

    def to_seconds(timestamp: str) -> float:
        hh, mm, rest = timestamp.split(":")
        ss, ms = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

    subtitles: List[SubtitleLine] = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        index = int(lines[0])
        start_str, end_str = lines[1].split(" --> ")
        text = " ".join(lines[2:])
        subtitles.append(
            SubtitleLine(
                index=index,
                start=to_seconds(start_str),
                end=to_seconds(end_str),
                text=text,
            )
        )
    return subtitles


def detect_player(preferred: str | None = None) -> PlayerChoice:
    """Return the first available audio player and its capabilities."""

    def build_choice(raw_cmd: List[str]) -> PlayerChoice:
        name = Path(raw_cmd[0]).name
        supports_seek = name == "mpv"
        return PlayerChoice(command=raw_cmd, name=name, supports_seek=supports_seek)

    candidates: List[PlayerChoice] = []
    if preferred:
        candidates.append(build_choice(shlex.split(preferred)))
    candidates.extend(
        [
            build_choice(["mpv", "--no-video"]),
            build_choice(["ffplay", "-nodisp", "-autoexit"]),
            build_choice(["afplay"]),
        ]
    )

    for candidate in candidates:
        if shutil.which(candidate.command[0]):
            return candidate
    raise RuntimeError(
        "找不到可用的音頻播放器，請先安裝 mpv/ffplay 或指定 --player"
    )


def play_audio(audio_path: Path, player: PlayerChoice) -> subprocess.Popen:
    """Spawn the audio player process without interactive control."""
    cmd = player.command + [str(audio_path)]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_show_simple(subtitles: List[SubtitleLine], limit: Optional[int] = None) -> bool:
    """Fallback subtitle renderer using a monotonic clock."""
    start_time = time.perf_counter()
    current_line = 0
    total = len(subtitles) if limit is None else min(limit, len(subtitles))

    try:
        while current_line < total:
            subtitle = subtitles[current_line]
            now = time.perf_counter() - start_time
            wait_time = subtitle.start - now
            if wait_time > 0:
                time.sleep(min(wait_time, 0.05))
                continue

            timestamp = format_timestamp(subtitle.start)
            duration = subtitle.end - subtitle.start
            print(f"\r[{timestamp} / +{duration:4.1f}s] {subtitle.text}      ")
            current_line += 1
    except KeyboardInterrupt:
        print("\n⏹️  手動停止字幕輸出。")
        return False
    return True


def run_show_interactive(
    subtitles: List[SubtitleLine],
    controller: MPVController,
    limit: Optional[int] = None,
    keyboard_enabled: bool = True,
) -> bool:
    renderer = SubtitleRenderer(subtitles, limit)
    playback_finished = True

    try:
        with KeyListener(enabled=keyboard_enabled) as listener:
            while True:
                if controller.poll() is not None:
                    break

                key = listener.poll_key(0.05)
                if key == "RIGHT":
                    controller.seek(SEEK_STEP_SECONDS)
                    print("\n⏩ 快進 15 秒")
                    continue
                if key == "LEFT":
                    controller.seek(-SEEK_STEP_SECONDS)
                    print("\n⏪ 快退 15 秒")
                    continue
                if key == "SPACE":
                    paused = controller.toggle_pause()
                    if paused:
                        print("\n⏸️ 暫停")
                    else:
                        print("\n▶️ 繼續播放")
                    continue

                current_time = controller.current_time()
                renderer.update(current_time)
                if renderer.finished:
                    break
    except KeyboardInterrupt:
        print("\n⏹️  手動停止字幕輸出。")
        playback_finished = False

    print()
    return playback_finished


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):02d}:{secs:05.2f}"


def main():
    parser = argparse.ArgumentParser(
        description="Play audio while displaying synchronized subtitles"
    )
    parser.add_argument("audio", type=Path, help="音頻檔案 (wav/mp3/...)")
    parser.add_argument("srt", type=Path, help="對應的 SRT 字幕")
    parser.add_argument(
        "--player",
        type=str,
        help="指定播放器指令，例如 'afplay' 或 'ffplay -nodisp -autoexit'",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="僅顯示字幕，不播放音頻 (用於除錯)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="只顯示前 N 筆字幕，方便預覽",
    )

    args = parser.parse_args()

    if not args.audio.exists():
        parser.error(f"音頻檔案不存在: {args.audio}")
    if not args.srt.exists():
        parser.error(f"SRT 檔案不存在: {args.srt}")

    subtitles = parse_srt(args.srt)
    if not subtitles:
        parser.error("SRT 沒有可用字幕內容")

    limit = None
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit 必須是正整數")
        limit = args.limit

    player_choice: Optional[PlayerChoice] = None
    controller: Optional[MPVController] = None
    audio_proc: Optional[subprocess.Popen] = None
    info_messages: List[str] = []

    if not args.mute:
        player_choice = detect_player(args.player)
        if player_choice.supports_seek:
            try:
                controller = MPVController(args.audio, player_choice.command)
                controller.start()
            except Exception as exc:  # pragma: no cover - interactive path
                info_messages.append(f"⚠️  無法啟用快進/快退：{exc}")
                if controller is not None:
                    controller.close()
                controller = None
        if controller is None:
            audio_proc = play_audio(args.audio, player_choice)
            if not player_choice.supports_seek:
                info_messages.append("⚠️  目前播放器不支援方向鍵快進/快退。")
            elif not info_messages:
                info_messages.append("⚠️  目前播放器沒有啟用快進/快退控制。")
        elif not sys.stdin.isatty():
            info_messages.append("⚠️  偵測到非互動式終端，方向鍵快進/快退停用。")
    else:
        info_messages.append("ℹ️  靜音模式僅顯示字幕，不會播放音頻。")

    print("▶️  開始播放... 按 Ctrl+C 可提前停止")
    if controller and sys.stdin.isatty():
        print("← → 快退/快進 15 秒")
        print("空白鍵 暫停/繼續")
    for message in info_messages:
        print(message)

    playback_finished = (
        run_show_interactive(subtitles, controller, limit=limit, keyboard_enabled=sys.stdin.isatty())
        if controller
        else run_show_simple(subtitles, limit=limit)
    )

    if controller:
        try:
            if not playback_finished:
                controller.terminate()
            controller.wait()
        finally:
            controller.close()
    elif audio_proc:
        if not playback_finished and audio_proc.poll() is None:
            audio_proc.terminate()
        audio_proc.wait()


if __name__ == "__main__":
    main()
