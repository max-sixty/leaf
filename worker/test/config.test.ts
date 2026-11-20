import { URL } from "node:url";
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
    scheduling_policy: string;
    images: Record<string, { dockerfile: string; build_context: string }>;
  }>;
  durable_objects: {
    bindings: Array<{ name: string; class_name: string }>;
  };
  migrations: Array<{
    tag: string;
    new_sqlite_classes?: string[];
    renamed_classes?: Array<{ from: string; to: string }>;
    deleted_classes?: string[];
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
const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
const codexConfig = parse(
  readFileSync(new URL("../codex-config.toml", import.meta.url), "utf8"),
) as Record<string, unknown>;
const workerSource = readFileSync(new URL("../src/index.ts", import.meta.url), "utf8");
const packageManifest = JSON.parse(
  readFileSync(new URL("../../package.json", import.meta.url), "utf8"),
) as { dependencies: Record<string, string> };

describe("deployment configuration", () => {
  it("lets each session object start its container from the image its code names", () => {
    const [binding] = config.durable_objects.bindings;
    const live = config.migrations.reduce((classes, migration) => {
      for (const created of migration.new_sqlite_classes ?? []) classes.add(created);
      for (const renamed of migration.renamed_classes ?? []) {
        classes.delete(renamed.from);
        classes.add(renamed.to);
      }
      for (const deleted of migration.deleted_classes ?? []) classes.delete(deleted);
      return classes;
    }, new Set<string>());

    expect(live.has(container.class_name)).toBe(true);
    expect(binding.class_name).toBe(container.class_name);
    expect(container.scheduling_policy).toBe("durable_object");
    expect(Object.keys(container.images)).toEqual(["leaf"]);
    expect(workerSource).toContain("image: container.images.leaf,");
  });

  it("keeps one bounded remote development environment away from leaf.page", () => {
    const dev = config.env.dev;
    const [devContainer] = dev.containers;

    expect(dev.name).toBe("leaf-website-dev");
    expect(dev.workers_dev).toBe(true);
    expect(dev.routes).toEqual([]);
    expect(devContainer.name).toBe("leaf-website-dev-session");
    expect({ ...devContainer, name: container.name }).toEqual(container);
    expect(dev.assets).toEqual(config.assets);
    expect(dev.secrets).toEqual(config.secrets);
    expect(dev.durable_objects).toEqual(config.durable_objects);
    expect(dev.migrations).toEqual(config.migrations);
    expect(dev.observability).toEqual(config.observability);
    expect(dev.ratelimits).toEqual(config.ratelimits);
    expect(dev.analytics_engine_datasets).toEqual([
      { binding: "WEBSITE_EVENTS", dataset: "leaf_website_events_dev" },
    ]);
  });

  it("bounds users’ task starts and model calls", () => {
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

  it("ships the pinned Codex harness, ready Leaf CLI, and complete Leaf plugin", () => {
    expect(packageManifest.dependencies["@openai/codex"]).toMatch(/^\d+\.\d+\.\d+$/);
    expect(dockerfile).toContain("/app/.venv/bin/leaf --version");
    expect(dockerfile).toContain("codex plugin add leaf@leaf --json");
    expect(dockerfile).toContain("codex-resources /codex-bin/codex-resources");
    expect(dockerfile).toContain("test -x /codex-bin/codex-resources/bwrap");
    expect(dockerfile).toContain("codex plugin marketplace add /app --json");
    expect(codexConfig).toMatchObject({
      model_provider: "leaf-http",
      model_providers: {
        "leaf-http": {
          name: "OpenAI",
          requires_openai_auth: true,
          supports_websockets: false,
          env_http_headers: {
            "OpenAI-Organization": "OPENAI_ORGANIZATION",
            "OpenAI-Project": "OPENAI_PROJECT",
          },
        },
      },
    });
    // Codex runs unsandboxed here, so the plugin's route out of the sandbox is off.
    expect(codexConfig.plugins).toEqual({
      "leaf@leaf": { mcp_servers: { leaf: { enabled: false } } },
    });
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
});
