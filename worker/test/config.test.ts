import { readFileSync } from "node:fs";

import { parse } from "smol-toml";
import { describe, expect, it } from "vitest";

interface DeploymentConfig {
  name: string;
  workers_dev?: boolean;
  routes?: unknown[];
  assets: Record<string, unknown>;
  containers: Array<{
    name: string;
    class_name: string;
    max_instances: number;
    instance_type: string;
    rollout_active_grace_period: number;
  }>;
  durable_objects: {
    bindings: Array<{ name: string; class_name: string }>;
  };
  vars: { AGENT_PREWARM: string };
  migrations: Array<{
    tag: string;
    new_sqlite_classes?: string[];
    renamed_classes?: Array<{ from: string; to: string }>;
  }>;
  analytics_engine_datasets: Array<{ binding: string; dataset: string }>;
  ratelimits: Array<{
    name: string;
    simple: { limit: number; period: number };
  }>;
  secrets: { required: string[] };
  observability: { enabled: boolean };
  env: { dev: DeploymentConfig };
}

const config = parse(
  readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8"),
) as unknown as DeploymentConfig;
const [container] = config.containers;
const dockerfile = readFileSync(
  new URL("../../Dockerfile.website", import.meta.url),
  "utf8",
);
const codexConfig = parse(
  readFileSync(new URL("../codex-config.toml", import.meta.url), "utf8"),
) as Record<string, unknown>;
const workerSource = readFileSync(
  new URL("../src/index.ts", import.meta.url),
  "utf8",
);
const packageManifest = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
) as { dependencies: Record<string, string> };

describe("deployment configuration", () => {
  it("keeps addressing the standing Cloudflare container application", () => {
    const [binding] = config.durable_objects.bindings;
    const [createdClass] = config.migrations[0].new_sqlite_classes ?? [];
    const deployedName = `${config.name}-${createdClass.toLowerCase()}`;

    expect(container.name).toBe(deployedName);
    expect(binding.class_name).toBe(container.class_name);
  });

  it("keeps one bounded remote development environment away from leaf.page", () => {
    const dev = config.env.dev;
    const [devContainer] = dev.containers;

    expect(dev.name).toBe("leaf-website-dev");
    expect(dev.workers_dev).toBe(true);
    expect(dev.routes).toEqual([]);
    expect(devContainer.name).toBe("leaf-website-dev-leafexamplesession");
    expect(devContainer.max_instances).toBe(10);
    expect({
      ...devContainer,
      name: container.name,
      max_instances: container.max_instances,
    }).toEqual(container);
    expect(dev.assets).toEqual(config.assets);
    expect(dev.secrets).toEqual(config.secrets);
    expect(dev.durable_objects).toEqual(config.durable_objects);
    expect(dev.migrations).toEqual(config.migrations);
    expect(dev.observability).toEqual(config.observability);
    expect(dev.ratelimits).toEqual(config.ratelimits);
    expect(dev.vars).toEqual(config.vars);
    expect(dev.analytics_engine_datasets).toEqual([
      { binding: "WEBSITE_EVENTS", dataset: "leaf_website_events_dev" },
    ]);
  });

  it("reserves ten basic container slots for development", () => {
    const [devContainer] = config.env.dev.containers;

    expect(container.max_instances + devContainer.max_instances).toBe(6_000);
    expect(container.instance_type).toBe("basic");
    expect(devContainer.instance_type).toBe("basic");
  });

  it("prewarms readers and bounds their task starts and model calls", () => {
    expect(config.vars.AGENT_PREWARM).toBe("true");
    expect(config.ratelimits).toEqual([
      {
        name: "SOURCE_AGENT_RATE_LIMITER",
        namespace_id: "34302",
        simple: { limit: 20, period: 60 },
      },
    ]);
  });

  it("binds the website event dataset", () => {
    expect(config.analytics_engine_datasets).toEqual([
      { binding: "WEBSITE_EVENTS", dataset: "leaf_website_events" },
    ]);
  });

  it("ships the pinned Codex host and the ready Leaf CLI without the authoring plugin", () => {
    expect(packageManifest.dependencies["@openai/codex"]).toBe("0.153.4");
    expect(dockerfile).toContain("/app/.venv/bin/leaf --version");
    expect(dockerfile).not.toContain("codex plugin add leaf@leaf");
    expect(dockerfile).toContain("codex-resources /codex-bin/codex-resources");
    expect(dockerfile).toContain("test -x /codex-bin/codex-resources/bwrap");
    expect(dockerfile).not.toContain("/opt/leaf-plugin");
    expect(codexConfig).not.toHaveProperty("plugins");
  });

  it("keeps the model's shell from inheriting the OpenAI credential", () => {
    expect(config.secrets.required).toEqual(["OPENAI_API_KEY"]);
    expect(codexConfig).toMatchObject({
      shell_environment_policy: {
        inherit: "all",
        exclude: ["OPENAI_API_KEY"],
      },
    });
  });

  it("registers the outbound handler through Cloudflare's inherited setter", () => {
    expect(workerSource).toContain("LeafWebsiteSession.outboundByHost = {");
    expect(workerSource).not.toContain("static outboundByHost = {");
  });
});
