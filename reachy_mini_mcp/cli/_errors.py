"""ReachyError and exit-code policy.

Every failure inside the CLI raises :class:`ReachyError`. The top-level
``main()`` catches it, formats via :mod:`reachy_mini_mcp.cli._output`, and exits
with :attr:`ReachyError.code`. This guarantees:

* no Python traceback leaks to stderr;
* every error has a structured shape ``{code, message, remediation}``;
* the exit-code policy is centralised in one place.

Modelled on guildmaster's ``guild.cli._errors`` (cite-don't-import).
"""

from __future__ import annotations

from dataclasses import dataclass

EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1
EXIT_ENV_ERROR = 2


@dataclass
class ReachyError(Exception):
    """Structured error raised within the CLI; carries a remediation hint."""

    code: int
    message: str
    remediation: str = ""

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "remediation": self.remediation,
        }
