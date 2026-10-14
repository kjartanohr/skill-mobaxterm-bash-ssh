#!/usr/bin/env python3
"""Loopback-only Cisco SG300-style SSH/CLI emulator for Expect testing."""

from __future__ import annotations

import argparse
import hmac
import logging
import socket
import threading
import time
from typing import Final

import paramiko

HOST: Final = "127.0.0.1"
PORT: Final = 22222
USERNAME: Final = "cisco"
PASSWORD: Final = "sg300-test-only"
HOSTNAME: Final = "cisco-sgc300"
CLI_TIMEOUT: Final = 120.0
MAX_LINE_LENGTH: Final = 1024

PASSWORD_EXPIRY_TEXT: Final = (
    "Your password has exceeded the maximum lifetime. "
    "Please change the password for better protection of your network.\r\n"
    "Do you want to change it now (Y/N)[N] ?"
)
VERSION_TEXT: Final = (
    "SW version    1.3.0.62 ( emulator )\r\n"
    "Boot version  1.1.0.6 ( emulator )\r\n"
    "HW version    V02\r\n"
)


class EmulatorState:
    def __init__(self, secondary_login: bool, password_expiry: bool) -> None:
        self.secondary_login = secondary_login
        self.password_expiry = password_expiry
        self.password_aging_enabled = password_expiry
        self.ssh_password_auth = True
        self.lock = threading.Lock()


class CiscoSg300Server(paramiko.ServerInterface):
    def __init__(self, state: EmulatorState) -> None:
        self.state = state
        self.shell_requested = threading.Event()
        self.username: str | None = None

    def check_auth_password(self, username: str, password: str) -> int:
        username_ok = hmac.compare_digest(username, USERNAME)
        password_ok = hmac.compare_digest(password, PASSWORD)
        if username_ok and password_ok:
            self.username = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(
        self,
        channel: paramiko.Channel,
        term: str,
        width: int,
        height: int,
        pixelwidth: int,
        pixelheight: int,
        modes: dict[int, int],
    ) -> bool:
        return True

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        self.shell_requested.set()
        return True

    def check_channel_exec_request(self, channel: paramiko.Channel, command: bytes) -> bool:
        return False


def _send(channel: paramiko.Channel, text: str) -> None:
    channel.sendall(text.encode("utf-8"))


def _read_line(channel: paramiko.Channel, timeout: float = 30.0) -> str | None:
    deadline = time.monotonic() + timeout
    buffer = bytearray()
    previous_was_cr = False
    while time.monotonic() < deadline and not channel.closed:
        if not channel.recv_ready():
            time.sleep(0.02)
            continue
        chunk = channel.recv(1)
        if not chunk:
            return None
        for value in chunk:
            if previous_was_cr and value == 10:
                previous_was_cr = False
                continue
            previous_was_cr = False
            if value in (10, 13):
                previous_was_cr = value == 13
                return buffer.decode("utf-8", errors="replace")
            if value in (8, 127):
                if buffer:
                    buffer.pop()
                continue
            if value >= 32:
                buffer.append(value)
                if len(buffer) > MAX_LINE_LENGTH:
                    return None
    return None


def _prompt(mode: str) -> str:
    return f"{HOSTNAME}({mode})# " if mode == "config" else f"{HOSTNAME}# "


def _command_output(command: str, mode: str, state: EmulatorState) -> tuple[str, str, bool]:
    normalized = " ".join(command.strip().lower().split())
    next_mode = mode
    close_session = False

    if not normalized:
        return "", next_mode, close_session
    if normalized in {"exit", "logout", "quit"}:
        if mode == "config":
            return "", "exec", close_session
        return "Connection closed by foreign host.\r\n", next_mode, True
    if normalized in {"end", "disable"} and mode == "config":
        return "", "exec", close_session
    if normalized in {"configure terminal", "conf t"} and mode == "exec":
        return "", "config", close_session
    if normalized == "show version":
        return VERSION_TEXT, next_mode, close_session
    if normalized == "show passwords configuration":
        with state.lock:
            aging = "Enabled" if state.password_aging_enabled else "Disabled"
            auth = "Enabled" if state.ssh_password_auth else "Disabled"
        output = (
            f"Passwords aging is {aging.lower()}.\r\n"
            "Passwords complexity is disabled.\r\n"
            "Minimal length: 8 characters\r\n"
            "Minimal classes: 3\r\n"
            "New password must be different than the current: Enabled\r\n"
            "Maximum consecutive same characters: 3\r\n"
            "New password must be different than the user name: Enabled\r\n"
            "New password must be different than the manufacturer name: Enabled\r\n"
            f"SSH password authentication is {auth.lower()}.\r\n"
        )
        return output, next_mode, close_session
    if normalized in {"show running-config", "show startup-config"}:
        with state.lock:
            aging = state.password_aging_enabled
            ssh_auth = state.ssh_password_auth
        lines = [
            "Building configuration...",
            "Current configuration:",
            "!",
            f"hostname {HOSTNAME}",
            "!",
            "ip ssh server",
        ]
        if ssh_auth:
            lines.append("ip ssh password-auth")
        if not aging:
            lines.append("passwords aging 0")
        lines.extend(["!", "end"])
        return "\r\n".join(lines) + "\r\n", next_mode, close_session
    if normalized == "ip ssh password-auth" and mode == "config":
        with state.lock:
            state.ssh_password_auth = True
        return "", next_mode, close_session
    if normalized == "no ip ssh password-auth" and mode == "config":
        with state.lock:
            state.ssh_password_auth = False
        return "", next_mode, close_session
    if normalized == "passwords aging 0" and mode == "config":
        with state.lock:
            state.password_aging_enabled = False
        return "", next_mode, close_session
    if normalized == "write" or normalized == "copy running-config startup-config":
        return "Copy succeeded\r\n", next_mode, close_session
    if normalized in {"help", "?"}:
        return "Help may be requested at any point by entering '?'.\r\n", next_mode, close_session
    if normalized == "show":
        return "% Incomplete command\r\n", next_mode, close_session
    return "% Unrecognized command\r\n", next_mode, close_session


def _emulate_cli(channel: paramiko.Channel, state: EmulatorState) -> None:
    if state.secondary_login:
        _send(channel, "\r\nUser Name:")
        username = _read_line(channel)
        if username is None or not hmac.compare_digest(username, USERNAME):
            _send(channel, "\r\n% Authentication failed\r\n")
            return
        _send(channel, "\r\nPassword:")
        password = _read_line(channel)
        if password is None or not hmac.compare_digest(password, PASSWORD):
            _send(channel, "\r\n% Authentication failed\r\n")
            return
        _send(channel, "\r\n")

    if state.password_expiry:
        _send(channel, "\r\n" + PASSWORD_EXPIRY_TEXT)
        answer = _read_line(channel)
        if answer is None or answer.strip().lower() not in {"n", "no"}:
            _send(channel, "\r\nPassword change is not implemented by this emulator.\r\n")
            return
        with state.lock:
            state.password_aging_enabled = False
        _send(channel, "\r\n")

    mode = "exec"
    _send(channel, "\r\n" + _prompt(mode))
    while not channel.closed:
        command = _read_line(channel, CLI_TIMEOUT)
        if command is None:
            return
        _send(channel, command + "\r\n")
        output, mode, close_session = _command_output(command, mode, state)
        if output:
            _send(channel, output)
        if close_session:
            return
        _send(channel, _prompt(mode))


def _serve_connection(client: socket.socket, address: tuple[str, int], host_key: paramiko.RSAKey, state: EmulatorState) -> None:
    transport: paramiko.Transport | None = None
    try:
        if address[0] != HOST:
            return
        transport = paramiko.Transport(client)
        transport.add_server_key(host_key)
        server = CiscoSg300Server(state)
        transport.start_server(server=server)
        channel = transport.accept(timeout=15)
        if channel is None or not server.shell_requested.wait(timeout=10):
            return
        _emulate_cli(channel, state)
    except (OSError, paramiko.SSHException):
        logging.info("A local emulator connection ended.")
    finally:
        if transport is not None:
            transport.close()
        try:
            client.close()
        except OSError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a test-only Cisco SG300-style SSH CLI bound to 127.0.0.1."
    )
    parser.add_argument("--port", type=int, default=PORT, help=f"TCP port (default: {PORT})")
    parser.add_argument(
        "--secondary-login",
        action="store_true",
        help="Emulate the post-SSH User Name/Password CLI prompts.",
    )
    parser.add_argument(
        "--password-expiry",
        action="store_true",
        help="Emulate the password-lifetime Y/N prompt; only N is supported.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Port must be between 1024 and 65535.")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    state = EmulatorState(args.secondary_login, args.password_expiry)
    host_key = paramiko.RSAKey.generate(2048)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((HOST, args.port))
        listener.listen(8)
        listener.settimeout(0.5)
    except OSError as exc:
        listener.close()
        raise SystemExit(f"Cannot listen on {HOST}:{args.port}: {exc}") from exc

    mode_text = []
    if args.secondary_login:
        mode_text.append("secondary-login")
    if args.password_expiry:
        mode_text.append("password-expiry")
    enabled_modes = ", ".join(mode_text) if mode_text else "current SG300 prompt flow"
    print(f"READY {HOST}:{args.port} ({enabled_modes})", flush=True)
    print(f"Test-only SSH username: {USERNAME}", flush=True)
    print(f"Test-only SSH password: {PASSWORD}", flush=True)
    print("Bound to IPv4 loopback only; press Ctrl+C to stop.", flush=True)

    try:
        while True:
            try:
                client, address = listener.accept()
            except socket.timeout:
                continue
            worker = threading.Thread(
                target=_serve_connection,
                args=(client, address, host_key, state),
                daemon=True,
            )
            worker.start()
    except KeyboardInterrupt:
        print("\nStopping emulator.", flush=True)
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
