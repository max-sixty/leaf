"""How Leaf writes a JSON value into text a model reads: a fenced `json` block,
indented one space.

Every value Leaf puts in a model's context as data, such as a delivery a hook hands a
turn, the thread a fork reads or the schema a model is told to answer in, goes through
`json_block`. The fence sets the value apart from the instructions around it, and the
indent shows its nesting, where a delivery on one line runs to thousands of characters
that read as one more line of prose. The maintainer chose this, and one space over a
wider indent, since each space costs every line of the value bytes that count against
a hook's context limit (`Harness.fits_hook_context`) and shows no more of the
structure. The limit is checked on the text the hook writes, so a delivery the indent
takes past it goes by pointer. Printing the value compactly, to fit more deliveries
inline, is the alternative a later change might reach for; it puts the value back on
one line among the instructions.

A value inside a sentence, such as a tool call's argument a fork's prompt names or a
value a finding quotes, stays inline as a word of that sentence (`json.dumps`,
`registry.schema.json_value`). A tool result that holds the value alone, such as
Codex's `leaf_delivery` tool output, has no instructions around it to set it apart
from. What a program reads stays as that program takes it: a command's output
(`leaf delivery read`, `--json`), which scripts and `jq` read, and records and wire
messages.

`read_json_block` reads a block back, for code that reads the text Leaf wrote, such as
`hook_transport.inline_delivery`.
"""

import json
from typing import Any

_OPENING = "```json\n"
_CLOSING = "\n```"


def json_block(value: object) -> str:
    """`value` as a fenced `json` block, indented one space."""
    return f"{_OPENING}{json.dumps(value, ensure_ascii=False, indent=1)}{_CLOSING}"


def read_json_block(text: str) -> tuple[Any, str]:
    """The value of the block `json_block` wrote at the start of `text`, and the
    lines after its closing fence; ValueError where `text` doesn't open with a whole
    block, as when it was cut short."""
    if not text.startswith(_OPENING):
        raise ValueError("the text opens with no JSON block")
    value, end = json.JSONDecoder().raw_decode(text, len(_OPENING))
    if not text.startswith(_CLOSING, end):
        raise ValueError("the JSON block has no closing fence")
    return value, text[end + len(_CLOSING) :].removeprefix("\n")
