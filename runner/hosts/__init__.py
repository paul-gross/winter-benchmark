"""Agent-host adapters behind one host-agnostic contract (protocol §control surface)."""

from hosts.base import HostRequest, HostResult
from hosts.claude_code import ClaudeCodeHost
from hosts.codex import CodexHost
from hosts.fake import FakeHost
from hosts.opencode import OpenCodeHost

HOSTS = {
    "claude": ClaudeCodeHost,
    "codex": CodexHost,
    "opencode": OpenCodeHost,
    "fake": FakeHost,
}

__all__ = ["HOSTS", "HostRequest", "HostResult"]
