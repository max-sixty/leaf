"""Local website harnesses and Worker runs own the listeners they announce."""

import json
import os
import urllib.request
from contextlib import ExitStack
from pathlib import Path

from interact_support import STATED_TIMEOUT, wait_for
from leaf_dev import ROOT
from leaf_dev.commands import verify_site


def test_local_worker_wrapper_announces_independent_bound_ports(tmp_path, spawn):
    """Use real Wrangler with tiny Workers; Docker is a separate release boundary."""
    roots = [tmp_path / "first", tmp_path / "second"]
    processes, origins = [], []
    with ExitStack() as stack:
        for root in roots:
            worker = root / "worker"
            (worker / "src").mkdir(parents=True)
            (root / "node_modules").symlink_to(ROOT / "node_modules")
            (root / "package.json").write_text("{}")
            source = worker / "src" / "index.ts"
            source.write_text(
                'export default { fetch() { return new Response("'
                + root.name
                + '"); } };'
            )
            config = root / "wrangler.json"
            config.write_text(
                json.dumps(
                    {
                        "name": "local-" + root.name,
                        "main": str(source),
                        "compatibility_date": "2026-09-01",
                    }
                )
            )
            log = root / "server.log"
            output = stack.enter_context(log.open("w"))
            process = spawn(
                [
                    "node",
                    str(Path(verify_site.__file__).with_name("wrangler_server.mjs")),
                    str(root),
                    str(config),
                    str(root / "state"),
                ],
                stdout=output,
                stderr=output,
                cwd=worker,
                env={**os.environ, "WRANGLER_SEND_METRICS": "false"},
            )
            processes.append(process)

            def announced(process=process, log=log):
                assert process.poll() is None, log.read_text()
                return verify_site.announced_origin(log, "local_worker_ready")

            origins.append(wait_for(announced, bool, failure=log.read_text))
        assert origins[0] != origins[1]
        for origin, expected in zip(origins, (b"first", b"second"), strict=True):
            with urllib.request.urlopen(origin + "/") as response:
                assert response.read() == expected
        processes[0].terminate()
        processes[0].wait(timeout=STATED_TIMEOUT)
        with urllib.request.urlopen(origins[1] + "/") as response:
            assert response.read() == b"second"
        processes[1].terminate()
        processes[1].wait(timeout=STATED_TIMEOUT)
