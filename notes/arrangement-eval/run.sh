#!/usr/bin/env bash
# One authoring run: a fresh agent writes one subject's page with one arm's Leaf,
# then revises it for a standing preference in the same session.
#
# Usage: run.sh <arms-dir> <arm> <subject> <n> <batch>
#   <arms-dir>  what make_arms.sh wrote: <arms-dir>/leaf and <arms-dir>/plain
#   <arm>       leaf | plain
#   <subject>   a file in subjects/, without the extension
#   <n>         run number, so repeats do not overwrite each other
#   <batch>     directory name under .tmp/arrangement-eval/runs/
#
# The child is `claude -p` from a scratch cwd outside any repository, with project-only
# settings and auto-memory off, so neither the user's CLAUDE.md, their memory, nor the
# installed Leaf plugin loads, and nothing it saves reaches them. Without the memory
# switch a child whose cwd sits in this checkout shares the repository's memory: in the
# first full run, children saved the standing preference there and later runs read it.
# It reads the arm's
# SKILL.md by path, as a host that loaded the skill would hand it over, and runs the
# arm's launcher through $LEAF. Its state home is the run's own, so no claim reaches
# this machine's real pages.
#
# Output in <run>: prompt-{1,2}.txt, stream-{1,2}.jsonl (the full trace), page/ (the
# page directory), phase1.html (index.html after the first phase), err-{1,2}.txt,
# work-dir (the child's scratch cwd).
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
arms=$(cd "$1" && pwd); arm=$2; subject=$3; n=$4; batch=$5
payload="$arms/$arm"
run="$root/.tmp/arrangement-eval/runs/$batch/$subject-$arm-$n"
rm -rf "$run"
mkdir -p "$run/state"
work=$(mktemp -d)
echo "$work" > "$run/work-dir"
page="$run/page"

export LEAF="$payload/bin/leaf"
export XDG_STATE_HOME="$run/state"
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
# A run's own temp dir: concurrent runs of the two arms otherwise write the same
# /tmp names (an export, a screenshot) and can read each other's.
export TMPDIR="$work/tmp"
mkdir -p "$TMPDIR"
model=${MODEL:-claude-opus-5-5}

{
  cat <<EOF
You have the Leaf skill. Its instructions are in $payload/skills/leaf/SKILL.md: read
that file first and follow it, resolving the references it names from
$payload/skills/leaf/. \$LEAF is set to its launcher, $LEAF.

Write the page at $page. This run is non-interactive: nobody will read the page in a
browser or answer in it. Treat the page as a finished record the user will rely on:
write it, run the pre-handover review including \`\$LEAF version check $page --render\`,
fix what the checks report, and stamp it. Don't start a server, set a status, or wait
for feedback. When the stamped page passes, reply with one line naming its path.

The user's request follows.

EOF
  cat "$here/subjects/$subject.md"
} > "$run/prompt-1.txt"

cat > "$run/prompt-2.txt" <<EOF
The user writes:

"A standing preference for all my pages from now on: I read them in a window about
900px wide, beside my editor. At that width, keep the page's summary, status, contents
or queue beside the main content rather than stacked above or below it."

Revise the page at $page to follow this preference. Check it again with
\`\$LEAF version check $page --render\`, fix what the checks report, and stamp it. As
before, don't start a server or wait for feedback. When it passes, reply with one line.
EOF

flags=(--model "$model" --setting-sources project --strict-mcp-config
  --permission-mode bypassPermissions --tools "Bash,Read,Write,Edit,Glob,Grep"
  --add-dir "$payload" --add-dir "$run" --output-format stream-json --verbose)

cd "$work" || exit 1
claude -p "$(cat "$run/prompt-1.txt")" "${flags[@]}" < /dev/null > "$run/stream-1.jsonl" 2> "$run/err-1.txt"
session=$(python3 -c '
import json, sys
for line in open(sys.argv[1]):
    d = json.loads(line)
    if d.get("type") == "result":
        print(d["session_id"])
' "$run/stream-1.jsonl")
[ -f "$page/index.html" ] && cp "$page/index.html" "$run/phase1.html"
if [ -n "$session" ]; then
  claude -p "$(cat "$run/prompt-2.txt")" --resume "$session" "${flags[@]}" < /dev/null > "$run/stream-2.jsonl" 2> "$run/err-2.txt"
fi
echo "$run done"
