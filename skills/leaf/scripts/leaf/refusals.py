"""The one way domain code turns a request down, and the reason it carries.

Code that refuses raises `Refused`, or a subclass a boundary dispatches on, such as
`EventRefused` or `StaleFileError`. Only a process or transport boundary turns one
into an outcome: `LeafGroup` and `__main__` print it and exit 1, the HTTP door answers
it with a status or records it as a fault, a detached child's `Handshake` hands it to
its parent, and a long-lived caller (the Codex adapter, the website) carries on. So a
refusal raised from a helper the server and a harness share cannot end their process,
and an exception that is not a refusal keeps its traceback rather than printing as one.

Imports nothing from Leaf, so the lowest module can raise it.
"""


class Refusal(str):
    """A gate's reason with separate words for the user whose gesture it refuses,
    where the reason names internals that user never sees."""

    user: str

    def __new__(cls, reason: str, user: str):
        refusal = super().__new__(cls, reason)
        refusal.user = user
        return refusal


class Refused(Exception):
    """A request this code turns down, with what to do about it.

    `str()` is the reason the agent or the command line reads. `user` is what a
    browser shows the person whose gesture it was: the reason itself, unless the gate
    worded it for them (`Refusal`)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.user = getattr(reason, "user", reason)
