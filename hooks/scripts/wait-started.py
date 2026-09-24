#!/usr/bin/env python3
"""PostToolUse hook — hands the agent the session-list closing rule when a
background `leaf wait` starts.

The decision is the command's own shape, read from `tool_input.command`: some
simple command in it runs a program named `leaf` with `wait` as its first
argument, after any `NAME=value` assignments, and the call runs in the
background. A command that only mentions the phrase — a grep pattern, a file
it prints, a heredoc it writes — starts no wait, and neither does the rest of
the payload: `tool_response` carries whatever the command printed.

Claude Code's `if` filter on the registration is a prefilter only. It passes
any command it cannot parse, and Codex, which runs the same `hooks.json`,
ignores it. A command that will not tokenize says nothing.
"""

import json
import os
import re
import shlex
import sys
from itertools import dropwhile

SEPARATORS = {";", "&", "&&", "|", "||", "|&", "(", ")", "\n"}
# A heredoc body is data, not commands: drop it before tokenizing.
HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.MULTILINE | re.DOTALL
)
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")


def starts_wait(command):
    command = HEREDOC.sub("\n", command)
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace = " \t\r"
    try:
        tokens = list(lexer)
    except ValueError:
        return False
    words = []
    for token in [*tokens, "\n"]:
        if token not in SEPARATORS:
            words.append(token)
            continue
        program, argument = [*dropwhile(ASSIGNMENT.match, words), None, None][:2]
        if program and os.path.basename(program) == "leaf" and argument == "wait":
            return True
        words = []
    return False


def main():
    payload = json.load(sys.stdin)
    tool_input = payload["tool_input"]
    if tool_input.get("run_in_background") and starts_wait(tool_input["command"]):
        root = os.environ["CLAUDE_PLUGIN_ROOT"]
        with open(os.path.join(root, "hooks", "wait-started.json")) as guidance:
            sys.stdout.write(guidance.read())


main()
