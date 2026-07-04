"""The host-agnostic control surface every agent-host adapter implements.

Inputs and outputs are identical for every host so cross-host results stay
comparable; each adapter absorbs its host's invocation, permission-posture,
and transcript-format differences. Per-repo branch/commit capture is the
runner's job (git inspection), never the adapter's, so it cannot vary by host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HostRequest:
    """Held-constant inputs (protocol §Held-constant controls)."""

    workdir: Path          # the agent's starting directory (workspace/checkout root)
    prompt: str            # the initial prompt, verbatim; nothing follows it
    model: str             # model parameter (e.g. haiku, sonnet, or an exact id)
    max_seconds: int       # generous boundary used only to break a stuck run
    out_dir: Path          # where the adapter writes transcript + final message


@dataclass
class HostResult:
    """Uniform outputs; efficiency fields are recorded, never scored."""

    stall_signal: str                  # completed | awaiting_input | boundary | crashed
    final_message: str = ""
    transcript_path: Path | None = None
    host_version: str = ""
    exit_code: int | None = None
    efficiency: dict = field(default_factory=dict)


class HostAdapter:
    """Base class: subclasses implement run() and version()."""

    name = "base"

    def run(self, request: HostRequest) -> HostResult:  # pragma: no cover - contract
        raise NotImplementedError

    def version(self) -> str:  # pragma: no cover - contract
        raise NotImplementedError
