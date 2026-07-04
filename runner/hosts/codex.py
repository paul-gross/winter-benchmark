"""Codex host adapter — STUB behind the shared contract (not yet validated).

Drop-in shape for `codex exec` non-interactive runs. Every non-host,
non-model control (prompt, boundary, capture surface) is identical to the
other adapters. Marked unvalidated: refusing to run keeps an unvalidated host
from silently contaminating a batch. Validate the invocation + transcript
parsing, then delete the guard.

Known caveat (protocol §Known limitations): the winter-workflow condition is
not host-portable; a codex winter-workflow cell is host-scoped, never pooled.
"""

from __future__ import annotations

import subprocess

from hosts.base import HostAdapter, HostRequest, HostResult

VALIDATED = False


class CodexHost(HostAdapter):
    name = "codex"

    def version(self) -> str:
        result = subprocess.run(["codex", "--version"], capture_output=True, text=True)
        return result.stdout.strip() or "unknown"

    def run(self, request: HostRequest) -> HostResult:
        if not VALIDATED:
            raise NotImplementedError(
                "codex adapter is a stub: validate `codex exec --model <id> "
                "--dangerously-bypass-approvals-and-sandbox` invocation, JSONL "
                "capture, and final-message extraction, then set VALIDATED = True"
            )
        # Intended shape (kept current with the contract):
        # codex exec --model {request.model} --cd {request.workdir} \
        #   --dangerously-bypass-approvals-and-sandbox --json {request.prompt}
        raise NotImplementedError
