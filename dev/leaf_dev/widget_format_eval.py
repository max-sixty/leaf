"""One-response syntax comparison, with the component runtime held fixed.

Promptfoo owns scheduling and results. This provider composes Leaf's existing
subscription inference transport/configuration, retaining raw text without schema
decoding, and checks the resulting fragment in one shared Leaf host. Semantic
grading is a separate blinded reading of the retained outputs, not a text heuristic.
"""

import json
import tempfile
import time
from copy import deepcopy
from html import escape
from pathlib import Path

import turbohtml
from playwright.sync_api import Error as PlaywrightError

from leaf.codex import (
    app_server_connect,
    app_server_handshake,
    app_server_request,
    private_app_server,
)
from leaf.inference import CODEX_CONFIG, CODEX_SERVER_ARGUMENTS
from leaf_dev import ROOT
from leaf_dev.arms import codex_home, codex_program, environment, run_leaf, serving
from leaf_dev.browser import headless_shell, load, tab

FIXTURES = ROOT / "evals/widget-formats"
MODEL = "gpt-6.1-sol"
EFFORT = "medium"
TAGS = {
    "section",
    "div",
    "h1",
    "h2",
    "h3",
    "p",
    "strong",
    "em",
    "small",
    "span",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "br",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "lf-ask",
    "lf-options",
    "lf-option",
    "form",
    "label",
    "input",
    "select",
    "option",
    "textarea",
    "button",
    "fieldset",
    "legend",
    "output",
}
ATTRS = {
    "id",
    "class",
    "title",
    "role",
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
    "aria-live",
    "choose",
    "multiple",
    "chosen",
    "for",
    "type",
    "name",
    "value",
    "required",
    "placeholder",
    "rows",
    "cols",
    "maxlength",
    "minlength",
    "selected",
    "checked",
    "disabled",
    "scope",
}
VOID = {"input", "br"}
HOST = """<!doctype html><html lang="en"><head><title>Atlas review</title>
<style>main{max-width:52rem}form{display:grid;gap:1rem}label{display:grid;gap:.3rem}
input,select,textarea,button{font:inherit}output{white-space:pre-wrap}</style>
</head><body><main>FRAGMENT</main>
<script type="module">
document.addEventListener("submit", event => {
  if (!(event.target instanceof HTMLFormElement)) return;
  event.preventDefault();
  const form = event.target;
  let receipt = form.querySelector("output");
  if (!receipt) { receipt = document.createElement("output"); form.append(receipt); }
  receipt.setAttribute("role", "status");
  receipt.hidden = false;
  receipt.textContent = "Draft recorded locally for review\\n" +
    JSON.stringify(Object.fromEntries(new FormData(form)), null, 2);
});
</script></body></html>
"""


def instructions(condition: str) -> str:
    shared = (FIXTURES / "controlled-contract.md").read_text()
    return shared + "\n\n" + (FIXTURES / f"controlled-{condition}.md").read_text()


def compile_tree(node: object) -> str:
    if isinstance(node, str):
        return escape(node)
    if not isinstance(node, dict) or set(node) != {"type", "props", "children"}:
        raise ValueError("Each element needs exactly type, props, children")
    tag, props, children = node["type"], node["props"], node["children"]
    if tag not in TAGS or not isinstance(props, dict) or not isinstance(children, list):
        raise ValueError(
            "Element needs an allowed type, object props and array children"
        )
    attributes = []
    for name, value in props.items():
        if name not in ATTRS or not isinstance(value, (str, bool)):
            raise ValueError(f"Attribute {name} must be allowed and string or boolean")
        if value is True:
            attributes.append(f" {name}")
        elif value is not False:
            attributes.append(f' {name}="{escape(value, quote=True)}"')
    if tag in VOID and children:
        raise ValueError(f"{tag} cannot have children")
    opening = f"<{tag}{''.join(attributes)}>"
    return (
        opening
        if tag in VOID
        else opening + "".join(map(compile_tree, children)) + f"</{tag}>"
    )


def fragment(answer: str, condition: str) -> str:
    result = compile_tree(json.loads(answer)) if condition == "json" else answer
    parsed = turbohtml.parse_fragment(result)
    roots = [
        node
        for node in parsed.children
        if not isinstance(node, turbohtml.Text) or node.data.strip()
    ]
    if (
        len(roots) != 1
        or not isinstance(roots[0], turbohtml.Element)
        or roots[0].tag != "section"
    ):
        raise ValueError(
            "Return one section root, without a document wrapper or code fences"
        )
    for node in parsed.iter_elements():
        if node is parsed:
            continue
        if node.tag not in TAGS:
            raise ValueError(f"Tag {node.tag} is outside the shared catalog")
        for name in node.attrs:
            if name not in ATTRS:
                raise ValueError(f"Attribute {name} is outside the shared catalog")
    return result


def infer(request: str, system: str, work: Path) -> dict:
    """Fresh isolated home and one ephemeral no-tools turn, raw text for both arms."""
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="leaf-format-inference-") as temporary:
        temporary = Path(temporary)
        home = temporary / "home"
        home.mkdir()
        config_home = codex_home(home / ".codex")
        cwd = temporary / "cwd"
        cwd.mkdir()
        env = environment(HOME=str(home), CODEX_HOME=str(config_home))
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            env.pop(name, None)
        with private_app_server(
            str(codex_program()),
            env=env,
            arguments=CODEX_SERVER_ARGUMENTS,
            cwd=str(cwd),
            log_path=work / "app-server.log",
        ) as (endpoint, _):
            socket = app_server_connect(endpoint)
            trace = []
            first_text = None
            usage = None
            answers = []
            item_types = []

            def hear(message):
                nonlocal first_text, usage
                trace.append(
                    {
                        "elapsedMs": round((time.monotonic() - started) * 1000),
                        "message": message,
                    }
                )
                method, params = message.get("method"), message.get("params") or {}
                if (
                    method == "item/agentMessage/delta"
                    and params.get("delta")
                    and first_text is None
                ):
                    first_text = time.monotonic()
                if method == "thread/tokenUsage/updated":
                    usage = params["tokenUsage"]["last"]
                if method == "item/completed":
                    item = params["item"]
                    item_types.append(item["type"])
                    if item["type"] == "agentMessage":
                        answers.append(item)

            try:
                app_server_handshake(socket, 0, "leaf-format-eval", "Leaf format eval")
                config = deepcopy(CODEX_CONFIG)
                # Removed in the installed CLI; do not imply it enforces no tools.
                config.pop("include_apply_patch_tool", None)
                config["model_reasoning_effort"] = EFFORT
                params = {
                    "model": MODEL,
                    "serviceTier": "default",
                    "cwd": str(cwd),
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "baseInstructions": system,
                    "config": config,
                }
                thread = app_server_request(socket, "thread/start", 1, params, hear)
                turn_params = {
                    "threadId": thread["thread"]["id"],
                    "input": [{"type": "text", "text": request}],
                    "effort": EFFORT,
                    "serviceTierForTurn": "default",
                }
                turn_started = time.monotonic()
                (work / "request.json").write_text(
                    json.dumps(
                        {"threadStart": params, "turnStart": turn_params}, indent=2
                    )
                )
                (work / "thread.json").write_text(json.dumps(thread, indent=2))
                app_server_request(socket, "turn/start", 2, turn_params, hear)
                while True:
                    message = json.loads(socket.recv(timeout=300))
                    hear(message)
                    if message.get("method") == "turn/completed":
                        terminal = message["params"]["turn"]
                        break
                completed = time.monotonic()
            finally:
                socket.close()
                (work / "notifications.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in trace)
                )
    final = [item for item in answers if item.get("phase") == "final_answer"]
    if len(final) != 1:
        raise RuntimeError(f"Expected one final answer, received {len(final)}")
    no_tools = all(
        kind in {"userMessage", "agentMessage", "reasoning"} for kind in item_types
    )
    return {
        "text": final[0]["text"],
        "terminal": terminal,
        "usage": usage,
        "outputBytes": len(final[0]["text"].encode()),
        "noTools": no_tools,
        "itemTypes": item_types,
        "timing": {
            "setupMs": round((turn_started - started) * 1000),
            "turnMs": round((completed - turn_started) * 1000),
            "firstTextMs": round((first_text - turn_started) * 1000)
            if first_text
            else None,
            "requestTotalMs": round((completed - started) * 1000),
        },
    }


def check(answer: str, condition: str, case: str, work: Path) -> dict:
    checks = {
        "format-valid": False,
        "page-valid": False,
        "interaction-proven": case == "status",
    }
    try:
        content = fragment(answer, condition)
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        return {"checks": checks, "diagnostics": str(error)}
    checks["format-valid"] = True
    page, state = work / "page", work / "state"
    run_leaf(ROOT, state, "page", "init", str(page), check=True)
    (page / "index.html").write_text(HOST.replace("FRAGMENT", content))
    (work / "fragment.html").write_text(content)
    result = run_leaf(ROOT, state, "page", "check", str(page))
    diagnostics = result.stdout + result.stderr
    (work / "check.txt").write_text(diagnostics)
    checks["page-valid"] = result.returncode == 0
    interaction = None
    initial_choice = None
    if checks["page-valid"]:
        with (
            serving(ROOT, state, page) as url,
            headless_shell() as browser,
            tab(browser, viewport=(900, 760)) as view,
        ):
            errors = []
            view.on("pageerror", lambda error: errors.append(str(error)))
            load(view, url)
            (work / "visible.txt").write_text(view.locator("main").inner_text())
            view.screenshot(path=work / "before.png", full_page=True)
            try:
                if case == "choice":
                    options = view.locator("main lf-option")
                    initial_choice = options.evaluate_all(
                        "nodes => nodes.map(node => ({text: node.innerText, chosen: node.hasAttribute('chosen')}))"
                    )
                    if options.count() != 3:
                        raise AssertionError(
                            f"Expected three options, got {options.count()}"
                        )
                    assert not any(option["chosen"] for option in initial_choice), (
                        "A choice is already recorded before the user decides"
                    )
                    for index in (1, 2):
                        options.nth(index).click()
                        view.wait_for_function(
                            "index => [...document.querySelectorAll('main lf-option')].every((o, i) => o.hasAttribute('chosen') === (i === index))",
                            arg=index,
                        )
                    interaction = (
                        "Selection moved between options, leaving exactly one chosen"
                    )
                elif case == "form":
                    view.get_by_role("textbox", name="Title", exact=True).fill(
                        "Atlas review probe"
                    )
                    view.get_by_role(
                        "textbox", name="Customer impact", exact=True
                    ).fill("37 EU workspaces saw stale results")
                    view.get_by_role(
                        "combobox", name="Severity", exact=True
                    ).select_option(label="High")
                    view.locator("main form").get_by_role("button").click()
                    receipt = view.locator("main form output")
                    receipt.wait_for(state="visible")
                    value = receipt.inner_text()
                    assert all(
                        text in value
                        for text in (
                            "Atlas review probe",
                            "High",
                            "37 EU workspaces saw stale results",
                        )
                    ), value
                    interaction = value
                checks["interaction-proven"] = True
            except (AssertionError, PlaywrightError) as error:
                diagnostics += f"\nInteraction failed: {type(error).__name__}: {error}"
            view.screenshot(path=work / "after.png", full_page=True)
            if errors:
                checks["page-valid"] = False
                diagnostics += f"\nBrowser errors: {errors}"
    return {
        "checks": checks,
        "diagnostics": diagnostics,
        "interaction": interaction,
        "initialChoice": initial_choice,
    }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config = options["config"]
    case = context["vars"]["case"]
    condition = config["condition"]
    samples = Path(config["samples"])
    samples.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f"{case}-{condition}-", dir=samples))
    original = context["vars"].get("repairOf")
    system = (
        (Path(original) / "instructions.txt").read_text()
        if original
        else instructions(condition)
    )
    (work / "instructions.txt").write_text(system)
    (work / "prompt.txt").write_text(prompt)
    result = infer(prompt, system, work)
    (work / "response.txt").write_text(result["text"])
    grading = check(result["text"], condition, case, work)
    metadata: dict = {
        "work": str(work),
        "case": case,
        "condition": condition,
        "repetition": context["vars"].get("repetition"),
        "stage": config.get("stage", "initial"),
        "repairOf": context["vars"].get("repairOf"),
        **{key: value for key, value in result.items() if key != "text"},
        **grading,
    }
    metadata["checks"]["completed"] = result["terminal"]["status"] == "completed"
    metadata["checks"]["no-tool-use"] = result["noTools"]
    (work / "sample.json").write_text(json.dumps(metadata, indent=2))
    usage = result["usage"] or {}
    return {
        "output": result["text"],
        "metadata": metadata,
        **(
            {
                "tokenUsage": {
                    target: usage[source]
                    for source, target in (
                        ("inputTokens", "prompt"),
                        ("outputTokens", "completion"),
                        ("totalTokens", "total"),
                    )
                    if source in usage
                }
            }
            if usage
            else {}
        ),
    }
