#!/usr/bin/env bash
# One authoring run: paste one arm's guidance and one subject into a single
# prompt and save the page body the model writes.
#
# Usage: run.sh <arm-dir> <subject> <n>
#   <arm-dir>  holds that arm's SKILL.md and authoring-decisions.md
#   <subject>  a .md file in this directory, without the extension
#   <n>        run number, so repeats do not overwrite each other
#
# Output lands in .tmp/ask-placement-eval/<subject>-<arm>-<n>.{html,json,err}
# under the repository root. README.md says how to stage the arms and score.
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$(dirname "$here")")
arm_dir=$1; subject=$2; n=$3
arm=$(basename "$arm_dir")
out_dir="$root/.tmp/ask-placement-eval"
mkdir -p "$out_dir"
out="$out_dir/$subject-$arm-$n"
prompt="$out.prompt"
{
  echo "You are an agent authoring a Leaf page. Follow the authoring guidance below exactly. Then write the page's complete <main> element for the subject that follows. Use only ordinary HTML (sections, headings, paragraphs, lists, tables, <details>/<summary>) plus these widgets: <lf-decision id=\"…\"><h2 or h3>the question</h2><lf-options id=\"…\" choose><lf-option id=\"…\"><strong>title</strong><p>case</p></lf-option>…</lf-options></lf-decision>; <lf-chart id=\"…\" kind=\"line\" y=\"label\"><pre>csv</pre></lf-chart>; <lf-diagram id=\"…\"><pre>mermaid</pre></lf-diagram>. Give every section, block, and widget an id. Output only the HTML of <main>, nothing else."
  echo
  echo "===== GUIDANCE: skill, Page contract ====="
  awk '/^## Page contract/{f=1} /^## Conditional references/{f=0} f' "$arm_dir/SKILL.md"
  echo
  echo "===== GUIDANCE: page-authoring.md, Reading cost ====="
  awk '/^## Reading cost/{f=1} /^## Pre-handover review/{f=0} f' "$root/skills/leaf/references/page-authoring.md"
  echo
  echo "===== GUIDANCE: authoring-decisions.md ====="
  cat "$arm_dir/authoring-decisions.md"
  echo
  echo "===== SUBJECT ====="
  cat "$here/$subject.md"
} > "$prompt"
# Run from an empty directory outside the repository: inside it, a project
# CLAUDE.md or the worktree layout joins the prompt and the model answers that.
cd "$(mktemp -d)" || exit 1
claude -p "$(cat "$prompt")" --setting-sources user --tools "" --strict-mcp-config --output-format json < /dev/null > "$out.json" 2> "$out.err"
python3 - "$out.json" "$out.html" <<'EOF'
import json
import sys

answer = json.load(open(sys.argv[1]))
open(sys.argv[2], "w").write(answer.get("result", ""))
print(sys.argv[2], "is_error =", answer.get("is_error"))
EOF
