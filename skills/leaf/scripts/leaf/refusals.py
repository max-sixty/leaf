"""The one way domain code turns a request down, and the reason it carries.

Code that refuses raises `Refused`, or a subclass a boundary dispatches on, such as
`EventRefused` or `StaleFileError`. Only a process or transport boundary turns one
into an outcome: `LeafGroup` and `__main__` print it and exit 1, the HTTP door answers
it with a status or records it as a fault, a detached child's `Handshake` hands it to
its parent, and a long-lived caller (the Codex adapter, the website) carries on. So a
refusal raised from a helper the server and a harness share cannot end their process,
and an exception that is not a refusal keeps its traceback rather than printing as one.

A gate that refuses on what it found raises `findings.Rejected`, whose `findings` are
records with a code and fields; any other refusal has none. A boundary that answers
in JSON writes `json()`, so the event door's refusal answer and a command's refusal
have one shape.

Imports nothing from Leaf, so the lowest module can raise it.
"""


class Refused(Exception):
    """A request this code turns down, with what to do about it.

    `str()` is the reason the agent or the command line reads. `user` is what a
    browser shows the person whose gesture it was: the reason itself, unless the gate
    worded it for them (`findings.Rejected`)."""

    findings: tuple = ()

    def __init__(self, reason: str):
        super().__init__(reason)
        self.user = reason

    def json(self) -> dict:
        """The refusal as a JSON reader takes it: its words, and the record of each
        finding it refused on (`findings.Finding.json`), less the words `error`
        already carries."""
        return {
            "error": str(self),
            "findings": [finding.json(text=False) for finding in self.findings],
        }
