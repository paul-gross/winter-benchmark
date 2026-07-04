"""OpenCode host adapter — STUB behind the shared contract (not yet validated).

Drop-in shape for `opencode run` non-interactive runs; same contract, same
held-constant controls as every other adapter. Refuses to run until the
invocation and transcript capture are validated, so an unvalidated host can
never silently contaminate a batch.

Known caveat (protocol §Known limitations): the winter-workflow condition is
not host-portable; an opencode winter-workflow cell is host-scoped, never
pooled.
"""

from __future__ import annotations

import subprocess

from hosts.base import HostAdapter, HostRequest, HostResult

VALIDATED = False


class OpenCodeHost(HostAdapter):
    name = "opencode"

    def version(self) -> str:
        result = subprocess.run(["opencode", "--version"], capture_output=True, text=True)
        return result.stdout.strip() or "unknown"

    def run(self, request: HostRequest) -> HostResult:
        if not VALIDATED:
            raise NotImplementedError(
                "opencode adapter is a stub: validate `opencode run --model <id>` "
                "invocation, permission posture, transcript capture, and "
                "final-message extraction, then set VALIDATED = True"
            )
        # Intended shape (kept current with the contract):
        # opencode run --model {request.model} --print-logs {request.prompt}  (cwd=workdir)
        raise NotImplementedError
