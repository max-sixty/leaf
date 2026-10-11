/**
 * Promptfoo transport for blinded UI defect detection. A candidate manifest names
 * only its prompt, screenshots or source files, and optional fixture URL. Gold
 * answers never enter this module. Both model families receive the same evidence
 * and browser operation; native transports are recorded as experimental factors.
 *
 * Codex subscription requests use pi-ai's OAuth Responses transport with an explicit
 * tool list. Claude uses the installed Agent SDK with built-ins disabled. Browser
 * access is one host-owned operation, never model-written JavaScript or shell code.
 * Each call owns a fresh conversation, browser context, and auditable evidence dir.
 * Model work has no wall-clock deadline. Timed progress reports expose elapsed
 * time and time since native activity without cancelling a slow conversation.
 */
import { createHash } from "node:crypto";
import {
  mkdtemp,
  mkdir,
  readFile,
  writeFile,
  appendFile,
  copyFile,
  symlink,
  access,
  rm,
} from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import path from "node:path";
import { stream } from "@earendil-works/pi-ai/api/openai-codex-responses";
import { normalizeContext } from "@earendil-works/pi-ai";
import { chromium } from "playwright";
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

const SYSTEM =
  'You are reviewing a user interface. Assess the supplied evidence, explain any concrete problems you can establish, and distinguish uncertainty from observation. Do not change the interface. Return your final assessment as JSON with fields verdict ("ready", "needs-work", or "insufficient-evidence"), findings (an array of objects with title, evidence, and consequence), and uncertainties (an array of strings).';
const BROWSER_DESCRIPTION =
  "Inspect the candidate interface. snapshot returns its current screenshot, visible text, Playwright accessibility snapshot, and numbered controls. Controls labelHint is a locator hint, not a computed accessible name; consult accessibility for accessible names, roles and state. click uses a control index or an exact button accessible name. press sends one keyboard key or chord. scroll moves the document or a numbered scrollable control. Every operation returns a new snapshot. Only the candidate fixture is reachable.";
const browserDescription = (limit) =>
  `${BROWSER_DESCRIPTION} You may make at most ${limit} total browser operations, including snapshots and failed operations. Each snapshot reports remainingOperations. Finish your final assessment before requesting another operation when none remain.`;
const BROWSER_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    action: { type: "string", enum: ["snapshot", "click", "press", "scroll"] },
    index: { type: "integer", minimum: 0 },
    name: { type: "string" },
    key: { type: "string" },
    x: { type: "number" },
    y: { type: "number" },
  },
  required: ["action"],
};
const browserZod = {
  action: z.enum(["snapshot", "click", "press", "scroll"]),
  index: z.number().int().nonnegative().optional(),
  name: z.string().optional(),
  key: z.string().optional(),
  x: z.number().optional(),
  y: z.number().optional(),
};
const digest = (value) => createHash("sha256").update(value).digest("hex");
const json = (value) => JSON.stringify(value, null, 2) + "\n";

function contained(root, name) {
  const target = path.resolve(root, name);
  if (target !== root && !target.startsWith(root + path.sep))
    throw new Error("Candidate path escapes its directory");
  return target;
}

function sanitized(value, secrets = []) {
  return JSON.parse(
    JSON.stringify(value, (key, item) => {
      if (/^(apiKey|access_token|refresh_token|authorization|cookie)$/i.test(key))
        return "[redacted]";
      if (typeof item !== "string") return item;
      for (const secret of secrets)
        if (secret) item = item.split(secret).join("[redacted]");
      if (item.startsWith("data:image/"))
        return `[image data URL; sha256=${digest(item)}; characters=${item.length}]`;
      if (key === "data" && item.length > 1000)
        return `[binary data; sha256=${digest(item)}; characters=${item.length}]`;
      return item;
    }),
  );
}

/** A single controlled browser capability shared by both model transports. */
export async function openBrowser(manifest, evidenceDir, limit = 12) {
  const fixture = new URL(manifest.url);
  if (
    !["http:", "https:"].includes(fixture.protocol) ||
    !["localhost", "127.0.0.1", "[::1]"].includes(fixture.hostname)
  )
    throw new Error("Browser fixture must use a loopback HTTP(S) URL");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({
      viewport: manifest.viewport ?? { width: 1200, height: 900 },
      reducedMotion: "reduce",
    });
    await context.route("**/*", async (route) => {
      const request = route.request(),
        url = new URL(request.url());
      const sameOrigin = url.origin === fixture.origin;
      const candidateNavigation =
        !request.isNavigationRequest() ||
        (url.pathname === fixture.pathname && url.search === fixture.search);
      if (sameOrigin && candidateNavigation) await route.continue();
      else await route.abort("blockedbyclient");
    });
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    await page.goto(fixture.href, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    let calls = 0;
    const captures = [];
    async function snapshot() {
      const controls = await page.evaluate(() => {
        const candidates = [...document.querySelectorAll("*")].filter((el) => {
          const style = getComputedStyle(el);
          return (
            el.matches(
              'button, summary, input, select, textarea, a[href], [role="button"], [role="slider"], [tabindex]',
            ) ||
            (/(auto|scroll)/.test(style.overflowY) &&
              el.scrollHeight > el.clientHeight) ||
            (/(auto|scroll)/.test(style.overflowX) && el.scrollWidth > el.clientWidth)
          );
        });
        const visible = candidates.filter((el) => {
          const r = el.getBoundingClientRect(),
            style = getComputedStyle(el);
          return (
            r.width > 0 &&
            r.height > 0 &&
            style.visibility !== "hidden" &&
            style.display !== "none"
          );
        });
        return visible.map((el, index) => {
          el.setAttribute("data-eval-control", String(index));
          const style = getComputedStyle(el);
          return {
            index,
            tag: el.tagName.toLowerCase(),
            labelHint:
              el.getAttribute("aria-label") ||
              el.innerText ||
              el.getAttribute("title") ||
              "",
            value: el.value ?? null,
            disabled: !!el.disabled,
            scrollable: {
              x:
                /(auto|scroll)/.test(style.overflowX) &&
                el.scrollWidth > el.clientWidth,
              y:
                /(auto|scroll)/.test(style.overflowY) &&
                el.scrollHeight > el.clientHeight,
            },
            scrollTop: el.scrollTop,
            scrollLeft: el.scrollLeft,
          };
        });
      });
      const visibleText = await page.locator("body").innerText();
      const accessibility = await page.locator("body").ariaSnapshot();
      const screenshot = await page.screenshot();
      const file = `browser-${String(calls).padStart(2, "0")}.png`;
      await writeFile(path.join(evidenceDir, file), screenshot);
      captures.push(file);
      return [
        {
          type: "text",
          text: JSON.stringify({
            visibleText,
            accessibility,
            controls,
            remainingOperations: Math.max(0, limit - calls),
          }),
        },
        { type: "image", data: screenshot.toString("base64"), mimeType: "image/png" },
      ];
    }
    return {
      captures,
      get calls() {
        return calls;
      },
      async invoke(args) {
        if (++calls > limit)
          throw new Error(`Browser tool budget exhausted (${limit} calls)`);
        if (!BROWSER_SCHEMA.properties.action.enum.includes(args.action))
          throw new Error("Unknown browser operation");
        if (args.action === "click") {
          if (args.index === undefined && !args.name)
            throw new Error("click requires a control index or exact name");
          const target =
            args.index !== undefined
              ? page.locator(`[data-eval-control="${Number(args.index)}"]`)
              : page.getByRole("button", { name: args.name, exact: true });
          if ((await target.count()) !== 1)
            throw new Error("click must identify exactly one current control");
          await target.click();
        } else if (args.action === "press") {
          if (
            !/^(?:(?:Shift|Control|Alt|Meta)\+)*(?:Enter|Escape|Space|Tab|ArrowLeft|ArrowRight|ArrowUp|ArrowDown|Home|End|PageUp|PageDown|[a-z0-9])$/.test(
              args.key ?? "",
            )
          )
            throw new Error("Unsupported keyboard key");
          await page.keyboard.press(args.key === "Space" ? " " : args.key);
        } else if (args.action === "scroll") {
          const x = Math.max(-2000, Math.min(2000, args.x ?? 0));
          const y = Math.max(-2000, Math.min(2000, args.y ?? 500));
          if (args.index === undefined) await page.mouse.wheel(x, y);
          else
            await page
              .locator(`[data-eval-control="${Number(args.index)}"]`)
              .evaluate((el, amount) => el.scrollBy(...amount), [x, y]);
        }
        await page.evaluate(
          () =>
            new Promise((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(resolve)),
            ),
        );
        return snapshot();
      },
      close: () => browser.close(),
    };
  } catch (error) {
    await browser.close();
    throw error;
  }
}

async function codexModel(config, content, browser, record) {
  const authHome = process.env.CODEX_HOME || path.join(homedir(), ".codex");
  const auth = JSON.parse(await readFile(path.join(authHome, "auth.json"), "utf8"));
  const accessToken = auth.tokens.access_token;
  const claims = JSON.parse(
    Buffer.from(accessToken.split(".")[1], "base64url").toString(),
  );
  if (claims.exp * 1000 < Date.now() + 60_000)
    throw new Error(
      "Codex access token expires within one minute; refresh the host login before running",
    );
  const catalog = JSON.parse(
    await readFile(path.join(authHome, "models_cache.json"), "utf8"),
  );
  const observed = catalog.models.find((item) => item.slug === config.model);
  if (!observed)
    throw new Error("Requested model is absent from current Codex metadata");
  const model = {
    id: config.model,
    name: config.model,
    api: "openai-codex-responses",
    provider: "openai-codex",
    baseUrl: "https://chatgpt.com/backend-api",
    input: observed.input_modalities,
    reasoning: true,
    contextWindow: observed.context_window,
    maxTokens: 16_384,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  };
  const tools = browser
    ? [
        {
          name: "browser",
          description: browserDescription(config.toolBudget ?? 12),
          parameters: BROWSER_SCHEMA,
        },
      ]
    : [];
  const messages = [{ role: "user", content, timestamp: Date.now() }];
  const usage = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0 };
  const maxTurns = (config.toolBudget ?? 12) + 1;
  for (let turn = 0; turn < maxTurns; turn++) {
    const result = await stream(
      model,
      normalizeContext({ systemPrompt: SYSTEM, messages, tools }),
      {
        apiKey: accessToken,
        reasoningEffort: config.effort ?? "high",
        toolChoice: browser ? "auto" : "none",
        transport: "sse",
        onPayload(payload) {
          if (
            !browser &&
            ((payload.tools?.length ?? 0) !== 0 || payload.tool_choice !== "none")
          )
            throw new Error("No-tools request contract violated");
          if (browser && payload.tools?.some((t) => t.name !== "browser"))
            throw new Error("Unexpected tool in browser condition");
          record("request", sanitized(payload, [accessToken]));
        },
        onProviderStreamEvent(event) {
          record("provider-event", sanitized(event, [accessToken]));
        },
      },
    ).result();
    record("assistant", sanitized(result, [accessToken]));
    for (const key of Object.keys(usage)) usage[key] += result.usage?.[key] ?? 0;
    if (["error", "aborted", "length", "deferred"].includes(result.stopReason))
      throw new Error(
        `Model did not complete: ${result.stopReason}: ${result.errorMessage ?? ""}`,
      );
    messages.push(result);
    const calls = result.content.filter((item) => item.type === "toolCall");
    if (!calls.length)
      return {
        output: result.content
          .filter((item) => item.type === "text")
          .map((item) => item.text)
          .join("\n"),
        usage,
        model: result.responseModel ?? result.model,
        nativeHarness: "pi-ai/openai-codex-responses",
        nativeSystemPrompt: SYSTEM,
      };
    for (const call of calls) {
      if (!browser || call.name !== "browser")
        throw new Error(`Unexpected model tool: ${call.name}`);
      record("tool-call", call);
      let content,
        isError = false;
      try {
        content = await browser.invoke(call.arguments);
      } catch (error) {
        if (/budget exhausted/.test(error.message)) throw error;
        content = [
          { type: "text", text: `Browser operation failed: ${error.message}` },
        ];
        isError = true;
      }
      record("tool-result", sanitized(content));
      messages.push({
        role: "toolResult",
        toolCallId: call.id,
        toolName: call.name,
        content,
        isError,
        timestamp: Date.now(),
      });
    }
  }
  throw new Error(`Model turn budget exhausted (${maxTurns} turns)`);
}

async function claudeModel(config, content, browser, record, evidenceDir) {
  const isolated = await mkdtemp(path.join(tmpdir(), "leaf-ui-reader-"));
  try {
    const home = path.join(isolated, "home"),
      cwd = path.join(isolated, "cwd");
    await mkdir(home, { mode: 0o700 });
    await mkdir(cwd);
    const keychains = path.join(homedir(), "Library", "Keychains");
    try {
      await access(keychains);
      await mkdir(path.join(home, "Library"));
      await symlink(keychains, path.join(home, "Library", "Keychains"));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    const hostClaude = process.env.CLAUDE_CONFIG_DIR || path.join(homedir(), ".claude");
    try {
      await access(path.join(hostClaude, ".credentials.json"));
      await mkdir(path.join(home, ".claude"), { recursive: true });
      await copyFile(
        path.join(hostClaude, ".credentials.json"),
        path.join(home, ".claude", ".credentials.json"),
      );
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    const env = Object.fromEntries(
      Object.entries(process.env).filter(
        ([key]) =>
          !key.startsWith("CLAUDE") &&
          !key.startsWith("CODEX") &&
          !key.startsWith("ANTHROPIC_") &&
          !["OPENAI_API_KEY", "CODEX_API_KEY"].includes(key),
      ),
    );
    Object.assign(env, { HOME: home, CLAUDE_CODE_DISABLE_AUTO_MEMORY: "1" });
    const abortController = new AbortController();
    let budgetError = null;
    const mcpServers = browser
      ? {
          candidate: createSdkMcpServer({
            name: "candidate",
            alwaysLoad: true,
            tools: [
              tool(
                "browser",
                browserDescription(config.toolBudget ?? 12),
                browserZod,
                async (args) => {
                  record("tool-call", args);
                  let items,
                    isError = false;
                  try {
                    items = await browser.invoke(args);
                  } catch (error) {
                    if (/budget exhausted/.test(error.message)) {
                      budgetError = error;
                      record("budget-limit", {
                        message: error.message,
                        limit: config.toolBudget ?? 12,
                      });
                      abortController.abort();
                      throw error;
                    }
                    items = [
                      {
                        type: "text",
                        text: `Browser operation failed: ${error.message}`,
                      },
                    ];
                    isError = true;
                  }
                  record("tool-result", sanitized(items));
                  return {
                    content: items.map((item) =>
                      item.type === "image"
                        ? { type: "image", data: item.data, mimeType: item.mimeType }
                        : item,
                    ),
                    isError,
                  };
                },
              ),
            ],
          }),
        }
      : {};
    // Keep the input stream open while SDK MCP operations run; close it with query.
    let release;
    async function* input() {
      const message = {
        type: "user",
        session_id: "",
        parent_tool_use_id: null,
        message: {
          role: "user",
          content: content.map((item) =>
            item.type === "image"
              ? {
                  type: "image",
                  source: {
                    type: "base64",
                    media_type: item.mimeType,
                    data: item.data,
                  },
                }
              : item,
          ),
        },
      };
      record("sdk-input", sanitized(message));
      yield message;
      await new Promise((resolve) => {
        release = resolve;
      });
    }
    const options = {
      model: config.model,
      cwd,
      env,
      tools: [],
      allowedTools: browser ? ["mcp__candidate__browser"] : [],
      mcpServers,
      strictMcpConfig: true,
      settingSources: [],
      settings: { autoMemoryEnabled: false, disableAllHooks: true },
      persistSession: false,
      permissionMode: "dontAsk",
      systemPrompt: SYSTEM,
      effort: config.effort ?? "high",
      maxTurns: (config.toolBudget ?? 12) + 1,
    };
    await writeFile(
      path.join(evidenceDir, "native-options.json"),
      json({
        ...options,
        env: "[isolated login home; no ambient API keys]",
        mcpServers: browser ? ["candidate/browser"] : [],
      }),
    );
    options.abortController = abortController;
    const run = query({ prompt: input(), options });
    let final,
      initializedModel = null,
      responseModel = null;
    const assistantModels = new Set();
    try {
      for await (const message of run) {
        record("sdk-event", sanitized(message));
        if (message.type === "system" && message.subtype === "init") {
          initializedModel = message.model ?? null;
          const permitted = browser ? ["mcp__candidate__browser"] : [];
          if (message.tools?.some((name) => !permitted.includes(name)))
            throw new Error(
              `Unexpected Claude tool surface: ${message.tools.join(", ")}`,
            );
        }
        if (message.type === "assistant" && message.message?.model) {
          responseModel = message.message.model;
          assistantModels.add(responseModel);
        }
        if (message.type === "result") {
          final = message;
          break;
        }
      }
    } catch (error) {
      throw budgetError ?? error;
    } finally {
      release?.();
      run.close();
    }
    if (budgetError) throw budgetError;
    if (!final || final.subtype !== "success" || final.is_error)
      throw new Error(`Claude did not complete: ${final?.subtype ?? "no result"}`);
    const modelIdentity = {
      initializedModel,
      assistantModels: [...assistantModels],
      modelUsageKeys: Object.keys(final.modelUsage ?? {}),
    };
    await writeFile(
      path.join(evidenceDir, "native-model-identity.json"),
      json(modelIdentity),
    );
    await writeFile(
      path.join(evidenceDir, "native-model-usage.json"),
      json(final.modelUsage ?? {}),
    );
    return {
      output: final.result,
      usage: final.usage,
      model: responseModel ?? initializedModel,
      modelIdentity,
      nativeHarness: "claude-agent-sdk",
      nativeSystemPrompt: SYSTEM,
    };
  } finally {
    await rm(isolated, { recursive: true });
  }
}

export default class UiReviewDetectionProvider {
  constructor(options = {}) {
    this.config = options.config ?? {};
  }
  id() {
    return `ui-review-detection:${this.config.model}:${this.config.condition}`;
  }
  async callApi(prompt, context = {}) {
    const config = { ...this.config, ...context.prompt?.config };
    const manifestPath = path.resolve(
      context.vars?.manifest ?? config.manifest ?? prompt,
    );
    const candidateDir = path.dirname(manifestPath);
    const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
    if (!["no-tools", "browser", "code-only"].includes(config.condition))
      throw new Error("condition must be no-tools, browser or code-only");
    if (
      config.condition === "code-only" &&
      ((manifest.images ?? []).length || !manifest.sources?.length)
    )
      throw new Error("Code-only requires source files and zero images");
    if (
      !["gpt-6.1-sol", "gpt-6-astra", "claude-opus-5-5", "claude-fable-5-1"].includes(
        config.model,
      )
    )
      throw new Error("Use a pinned supported evaluation model");
    const root = path.resolve(config.evidenceDir ?? ".tmp/ui-review-detection/samples");
    await mkdir(root, { recursive: true });
    const evidenceDir = await mkdtemp(path.join(root, "sample-"));
    const startedAt = new Date().toISOString();
    const started = performance.now();
    let lastActivity = started;
    let activityCount = 0;
    let status = "running";
    let traceWrites = Promise.resolve();
    const record = (type, value) => {
      if (type !== "progress" && type !== "finished") {
        lastActivity = performance.now();
        activityCount++;
      }
      const event = {
        at: new Date().toISOString(),
        elapsedMs: performance.now() - started,
        type,
        value,
      };
      traceWrites = traceWrites.then(() =>
        appendFile(path.join(evidenceDir, "trace.jsonl"), JSON.stringify(event) + "\n"),
      );
    };
    const timing = () => ({
      startedAt,
      elapsedMs: performance.now() - started,
      sinceLastActivityMs: performance.now() - lastActivity,
      activityCount,
      status,
    });
    const progress = setInterval(() => {
      const value = timing();
      record("progress", value);
      console.error(
        `[ui-review ${config.model}/${config.condition} ${path.basename(evidenceDir)}] ` +
          `${(value.elapsedMs / 1000).toFixed(1)}s elapsed; ` +
          `${(value.sinceLastActivityMs / 1000).toFixed(1)}s since activity`,
      );
    }, 30_000);
    progress.unref();
    let browser;
    try {
      let request =
        prompt && path.resolve(prompt) !== manifestPath
          ? prompt
          : await readFile(contained(candidateDir, manifest.prompt), "utf8");
      const sources = [];
      if (config.condition === "code-only") {
        request +=
          "\n\nCandidate source files follow. No rendered screenshots or browser access are supplied.\n";
        for (const source of manifest.sources) {
          const bytes = await readFile(contained(candidateDir, source.file));
          sources.push({ path: source.path, sha256: digest(bytes) });
          request += `\n<file path=${JSON.stringify(source.path)}>\n${bytes.toString("utf8")}\n</file>\n`;
        }
      }
      await writeFile(path.join(evidenceDir, "request.md"), request);
      const content = [{ type: "text", text: request }];
      for (let index = 0; index < (manifest.images ?? []).length; index++) {
        const file = contained(candidateDir, manifest.images[index]),
          bytes = await readFile(file);
        const mimeType =
          file.endsWith(".jpg") || file.endsWith(".jpeg") ? "image/jpeg" : "image/png";
        await writeFile(
          path.join(
            evidenceDir,
            `initial-${index}${mimeType === "image/png" ? ".png" : ".jpg"}`,
          ),
          bytes,
        );
        if (manifest.evidenceLabels?.[index])
          content.push({ type: "text", text: manifest.evidenceLabels[index] });
        content.push({ type: "image", data: bytes.toString("base64"), mimeType });
      }
      await writeFile(
        path.join(evidenceDir, "candidate.json"),
        json({
          model: config.model,
          condition: config.condition,
          effort: config.effort ?? "high",
          manifest: sanitized(manifest),
          systemPrompt: SYSTEM,
          ...(config.condition === "code-only" ? { sources } : {}),
          images: content
            .filter((x) => x.type === "image")
            .map((x) => ({ sha256: digest(x.data), mimeType: x.mimeType })),
          billing: "signed-in subscription; dollar cost not measured",
        }),
      );
      if (config.condition === "browser")
        browser = await openBrowser(manifest, evidenceDir, config.toolBudget ?? 12);
      const result = config.model.startsWith("gpt-")
        ? await codexModel(config, content, browser, record)
        : await claudeModel(config, content, browser, record, evidenceDir);
      await writeFile(path.join(evidenceDir, "output.txt"), result.output);
      await writeFile(path.join(evidenceDir, "usage.json"), json(result.usage));
      const metadata = {
        evidenceDir,
        condition: config.condition,
        requestedModel: config.model,
        responseModel: result.model,
        ...(result.modelIdentity ? { modelIdentity: result.modelIdentity } : {}),
        effort: config.effort ?? "high",
        nativeHarness: result.nativeHarness,
        nativeSystemPrompt: result.nativeSystemPrompt,
        toolCalls: browser?.calls ?? 0,
        budgetExhausted: (browser?.calls ?? 0) > (config.toolBudget ?? 12),
        outputTokenLimit: null,
        billing: "subscription; dollar cost unmeasured",
      };
      await writeFile(path.join(evidenceDir, "metadata.json"), json(metadata));
      status = "completed";
      return {
        output: result.output,
        metadata,
        tokenUsage: config.model.startsWith("gpt-")
          ? {
              prompt: result.usage.input + result.usage.cacheRead,
              completion: result.usage.output,
              cached: result.usage.cacheRead,
              total: result.usage.totalTokens,
            }
          : {
              prompt:
                (result.usage.input_tokens ?? 0) +
                (result.usage.cache_read_input_tokens ?? 0) +
                (result.usage.cache_creation_input_tokens ?? 0),
              completion: result.usage.output_tokens ?? 0,
            },
      };
    } catch (error) {
      status = "failed";
      await writeFile(
        path.join(evidenceDir, "harness-error.json"),
        json({ name: error.name, message: error.message }),
      );
      const budgetExhausted = /budget exhausted/.test(error.message);
      return {
        error: `Evaluation ${budgetExhausted ? "budget limit" : "harness failure"}: ${error.message}`,
        metadata: { evidenceDir, harnessFailure: !budgetExhausted, budgetExhausted },
      };
    } finally {
      clearInterval(progress);
      record("finished", timing());
      try {
        await browser?.close();
      } finally {
        await traceWrites;
        await writeFile(path.join(evidenceDir, "timing.json"), json(timing()));
      }
    }
  }
}
