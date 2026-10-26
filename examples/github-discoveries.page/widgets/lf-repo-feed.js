/** A reading stream over one Leaf data source. Browsing stays in the tab and
 * creates no obligation. An explicit question starts agent work. GitHub ids
 * keep comments attached across refreshes; HeldReading protects reading place.
 */
import {
  LeafElement,
  html,
  nothing,
  repeat,
  offered,
  whileConnected,
  tabStore,
  HeldReading,
  keeps,
  publishOutput,
  threadActions,
  readThreads,
  quoted,
  loadMarkdown,
  markdownReady,
  renderMarkdown,
  unsafeHTML,
} from "/runtime/widget-api.js";

import { GitHubFeed } from "../github-feed.js";

const DISTANCES = [
  ["all", "For you"],
  ["home", "Your repos"],
  ["nearby", "Nearby"],
  ["discovery", "Discover"],
];
const TOPICS = [
  ["all", "Everything"],
  ["agents", "Agents"],
  ["tools", "Dev tools"],
  ["data", "Data & languages"],
];
const date = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "America/Los_Angeles",
});

// Markdown stays source evidence; resolve its relative links against its own home.
function sourceMarkdown(item) {
  const fragment = document.createElement("template");
  fragment.innerHTML = renderMarkdown(item.body);
  for (const link of fragment.content.querySelectorAll("a[href]"))
    link.setAttribute("href", new URL(link.getAttribute("href"), item.source_url).href);
  const imageBase =
    item.kind === "project"
      ? item.source_url
          .replace("https://github.com/", "https://raw.githubusercontent.com/")
          .replace("/blob/", "/")
      : item.source_url;
  for (const image of fragment.content.querySelectorAll("img[src]"))
    image.setAttribute("src", new URL(image.getAttribute("src"), imageBase).href);
  for (const image of fragment.content.querySelectorAll("img")) image.loading = "lazy";
  return fragment.innerHTML;
}

class RepoFeed extends LeafElement {
  // The captured feed, set by whoever hosts the widget: Leaf from the bound source (the
  // registry's `x-data.changes.property`), or null while that source has none.
  static properties = { value: { attribute: false } };

  // The Markdown renderer's load while a draw waits for it, which `updateComplete`
  // waits for too.
  #markdown;

  constructor() {
    super();
    this.value = null;
  }

  async getUpdateComplete() {
    const result = await super.getUpdateComplete();
    await this.#markdown;
    return result;
  }

  // Load the Markdown renderer, and draw again once it has loaded.
  #loadMarkdown() {
    this.#markdown ??= loadMarkdown().then(() => {
      this.#markdown = undefined;
      this.requestUpdate();
    });
  }

  setup() {
    this.distance = tabStore.get(`${this.id}:distance`) ?? "all";
    this.topic = tabStore.get(`${this.id}:topic`) ?? "all";
    this.limit = 12;
    this.workState = { busy: false, exhausted: false, error: "" };
    this.loading = false;
    this.github = new GitHubFeed();
    // The feed live exploration composed, which replaces the captured one in this tab.
    this.liveFeed = null;
    this.readAheadPaused = false;
    this.liveEnabled = false;
    this.#loadMarkdown();
    this.filtered = [];
    this.openedSources = new Set();
    this.news = new HeldReading(
      this,
      () => [...this.querySelectorAll(".feed-list")],
      () => this.requestUpdate(),
    );
    whileConnected(this, (signal) => {
      this.observer = new IntersectionObserver(
        (entries) => {
          if (
            entries.some((entry) => entry.isIntersecting && entry.target.isConnected) &&
            this.canAdvance &&
            !this.readAheadPaused
          )
            this.more();
        },
        { rootMargin: "350px" },
      );
      this.signal = signal;
      return () => this.observer.disconnect();
    });
  }

  choose(field, value) {
    this[field] = value;
    this.readAheadPaused = false;
    this.workState.exhausted =
      this.github.loaded && !this.github.hasMore(this.distance);
    tabStore.set(`${this.id}:${field}`, value);
    this.limit = 12;
    this.requestUpdate();
    this.performUpdate();
    if (
      this.liveEnabled &&
      this.filtered.length <= 24 &&
      !this.loading &&
      !this.workState.exhausted
    )
      void this.collect("more", { reveal: false });
  }

  get canAdvance() {
    return (
      this.limit < this.filtered.length ||
      (this.liveEnabled &&
        !this.loading &&
        !this.workState.error &&
        !this.workState.exhausted)
    );
  }

  async more() {
    if (this.limit < this.filtered.length) {
      this.limit += 12;
      this.requestUpdate();
      this.performUpdate();
      if (
        this.liveEnabled &&
        this.limit >= this.filtered.length - 12 &&
        !this.loading &&
        !this.workState.exhausted &&
        !this.workState.error
      )
        void this.collect("more", { reveal: false });
      return;
    }
    await this.collect("more");
  }

  async collect(action, { reveal = true } = {}) {
    if (!this.shown || this.loading) return;
    this.liveEnabled = true;
    this.loading = true;
    this.workState.error = "";
    this.workState.stage = "Reading GitHub…";
    this.requestUpdate();
    this.performUpdate();
    try {
      if (action === "refresh") {
        this.github.scanned.clear();
        this.github.exhausted = false;
        await this.github.discover();
      }
      const current = this.liveFeed || this.shown;
      const stories = await this.github.collect(
        current.items,
        this.distance,
        (stage) => {
          this.workState.stage = stage;
          this.requestUpdate();
        },
      );
      const value = {
        ...current,
        fetched_at: new Date().toISOString(),
        items:
          action === "refresh"
            ? [...stories, ...current.items]
            : [...current.items, ...stories],
      };
      this.liveFeed = value;
      publishOutput(this, "stories", value);
      this.workState.exhausted = !this.github.hasMore(this.distance);
      this.readAheadPaused = stories.length === 0;
      if (action === "more" && reveal) this.limit += 12;
    } catch (error) {
      this.workState.error = `${error.message} Live exploration needs a host-granted github connection and an active agent session for generation. The captured stories remain available.`;
    } finally {
      this.loading = false;
      this.requestUpdate();
    }
  }

  lfRevealDatum(key) {
    if (
      [...this.querySelectorAll("[data-change]")].some(
        (node) => node.dataset.change === key,
      )
    )
      return;
    const index = this.shown?.items.findIndex((item) => item.id === key) ?? -1;
    if (index < 0) return;
    this.distance = "all";
    this.topic = "all";
    this.limit = Math.max(this.limit, index + 1);
    this.requestUpdate();
    this.performUpdate();
  }

  ask(item) {
    const existing = readThreads().threads.find(
      (thread) =>
        thread.anchor?.section === this.id &&
        thread.anchor?.datum === item.id &&
        !thread.resolved,
    );
    if (existing) {
      void threadActions.open(existing.key, { part: "reply" });
      return;
    }
    const created = threadActions.create({
      text: `How does “${item.title}” in ${item.repo} connect to my work?\n\n${item.url}`,
      anchor: { section: this.id, datum: item.id },
    });
    if (created) void threadActions.open(created.key, { part: "thread" });
  }

  render() {
    const incoming = this.liveFeed || this.value;
    // Let updates through when the existing visible prefix stays in place, in any order.
    const ordered = incoming?.items.filter(
      (item) =>
        (this.distance === "all" || item.distance === this.distance) &&
        (this.topic === "all" || item.topic === this.topic),
    );
    if (
      !incoming ||
      (this.shown &&
        this.filtered
          .slice(0, this.limit)
          .every((item, index) => ordered[index]?.id === item.id))
    )
      this.news.release();
    this.shown = this.news.hold(incoming);
    if (!this.shown)
      return html`<p class="feed-empty">
        The stream is waiting for its first collection of repository changes.
      </p>`;
    const value = this.shown;
    this.filtered = value.items.filter(
      (item) =>
        (this.distance === "all" || item.distance === this.distance) &&
        (this.topic === "all" || item.topic === this.topic),
    );
    const shown = this.filtered.slice(0, this.limit);
    const pending = incoming && incoming !== this.shown;
    const freshCount = pending
      ? incoming.items.filter(
          (item) => !this.shown.items.some((old) => old.id === item.id),
        ).length
      : 0;
    const mode = DISTANCES.find(([key]) => key === this.distance)[1];
    return html` <div class="feed-layout">
      <aside class="feed-sidebar" aria-label="Explore the feed">
        <nav class="feed-distance" aria-label="Closeness">
          ${DISTANCES.map(([key, label]) => html`<button ${offered()} type="button" aria-pressed=${this.distance === key} @click=${() => this.choose("distance", key)}><span>${label}</span><span class="feed-nav-dot" aria-hidden="true"></span></button>`)}
        </nav>
        <p class="feed-aside-note">Follow a rabbit hole.<br />Leave the rest behind.</p>
        <details class="feed-about">
          <summary>About this page</summary>
          <p>
            Projects to try, capabilities to explore, and changes that matter to your
            work. Open a source for the evidence.
          </p>
          <p>
            Contribution, follows, stars and recency prioritize candidates. The host’s
            LLM then judges what is worth your attention. Scores help retrieval; they
            are not a prediction of your interest.
          </p>
          <p>
            Your repos use public contribution evidence captured when this page was
            authored. Stars and followed people are read from GitHub as the page
            explores. Nearby connects to followed owners; Discover goes further.
          </p>
          <p>
            The initial stories are a captured snapshot. Browsing and filtering it makes
            no API requests. Refresh or Find more starts live exploration; subsequent
            scrolling can read ahead. New stories live in this tab; reloading returns to
            the snapshot. Exports can browse the snapshot.
          </p>
          <p>
            Live exploration reads GitHub through a host-granted HTTP connection and
            asks Leaf’s LLM API to choose and explain useful finds. Each pass reads two
            repositories, up to three releases per repository, and unfamiliar project
            READMEs. The sample is bounded and public only.
          </p>
          <p>
            To enable it, claim the page with an agent session and grant the connection
            on the host. Put the credential in the host environment; never in this page.
            The allowance below covers HTTP requests, not LLM spending.
          </p>
          <pre><code>leaf connection bind PAGE github https://api.github.com --credential-env GITHUB_TOKEN --max-requests 200</code></pre>
          <p>
            Edit this page’s profile.js to choose another account and contribution
            evidence.
          </p>
        </details>
      </aside>
      <div class="feed-main">
        <header class="feed-topbar">
          <div class="feed-status">
            <h2>${mode}</h2>
            ${
              pending
                ? html`<button
                    ${offered("feed-news")}
                    @click=${() => this.admit(freshCount)}
                  >
                    ${freshCount ? `${freshCount} new ${freshCount === 1 ? "story" : "stories"}` : "Show refreshed stream"}<span
                      aria-hidden="true"
                    >
                      ↑</span
                    >
                  </button>`
                : html`<button
                    ${offered("feed-refresh")}
                    ?disabled=${this.loading}
                    @click=${() => this.collect("refresh")}
                    aria-label="Refresh the feed"
                  >
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M16 7a6.5 6.5 0 1 0 .2 5M16 3v4h-4" /></svg
                    ><span>Refresh</span>
                  </button>`
            }
          </div>
          <div class="feed-toolbar">
            <nav class="feed-topics" aria-label="Topics">
              ${TOPICS.map(([key, label]) => html`<button ${offered()} type="button" aria-pressed=${this.topic === key} @click=${() => this.choose("topic", key)}>${label}</button>`)}
            </nav>
            <span class="feed-live"
              ><span aria-hidden="true"></span
              >${this.liveEnabled ? "Live exploration" : "Captured discoveries"}</span
            >
          </div>
        </header>
        <div class="feed-list">
          ${repeat(
            shown,
            (item) => item.id,
            (item) => this.card(item),
          )}
        </div>
        ${!shown.length ? html`<p class="feed-empty">Quiet in this corner. Try Everything, or wander a little further.</p>` : nothing}
        <footer class="feed-end" aria-live="polite">
          ${
            pending
              ? html`<button
                    ${offered("button")}
                    @click=${() => this.admit(freshCount)}
                  >
                    Show new stories and keep going
                  </button>
                  <p>A few more finds are waiting to join the stream.</p>`
              : shown.length < this.filtered.length
                ? html`<button ${offered("feed-more")} @click=${() => this.more()}>
                      Keep wandering <span aria-hidden="true">↓</span></button
                    >${this.loading ? html`<p>Reading ahead for your next few finds…</p>` : nothing}`
                : this.loading
                  ? html`<div class="feed-loading">
                      <span class="feed-loading-dots" aria-hidden="true"
                        ><i></i><i></i><i></i
                      ></span>
                      <p>
                        ${this.workState.stage || "Following another thread on GitHub…"}
                      </p>
                      <p>
                        Reading sources and choosing useful finds. You can keep
                        browsing.
                      </p>
                    </div>`
                  : this.workState.error
                    ? html`<p>${this.workState.error}</p>
                        <button ${offered("button")} @click=${() => this.more()}>
                          Try again
                        </button>`
                    : this.workState.exhausted
                      ? html`<p>A good place to come up for air.</p>
                          <p>Refresh to check for new releases.</p>`
                      : html`<button
                            ${offered("feed-more")}
                            @click=${() => this.more()}
                          >
                            Find more <span aria-hidden="true">↓</span>
                          </button>
                          <p>
                            ${this.readAheadPaused ? "No strong finds in that batch. Continue to explore another pair of repositories." : this.liveEnabled ? "More stories arrive as you scroll." : "Explore live with a GitHub connection and an active agent session."}
                          </p>`
          }
        </footer>
      </div>
    </div>`;
  }

  admit(count) {
    this.limit += count;
    this.news.show();
  }

  sourceOpened(event, id) {
    if (!event.target.open) return;
    this.openedSources.add(id);
    if (!markdownReady()) this.#loadMarkdown();
    this.requestUpdate();
  }

  card(item) {
    const angle = {
      unlock: "New possibility",
      fix: "Rough edge gone",
      idea: "Worth a detour",
      release: "Fresh release",
    }[item.angle];
    const repo = item.repo.split("/").at(-1);
    const mark = repo
      .replace(/[^a-z0-9]/gi, "")
      .slice(0, 2)
      .toUpperCase();
    const days = Math.floor((Date.now() - new Date(item.at)) / 86400000);
    const when =
      days < 1
        ? "Today"
        : days === 1
          ? "Yesterday"
          : days < 7
            ? `${days}d ago`
            : date.format(new Date(item.at));
    return html`<article
      class="feed-card"
      data-change=${item.id}
      data-angle=${item.angle}
      data-topic=${item.topic}
    >
      <a
        class="feed-avatar"
        href=${`https://github.com/${item.repo}`}
        target="_blank"
        rel="noreferrer"
        aria-label=${item.repo}
        >${mark}</a
      >
      <div class="feed-story">
        <div class="feed-meta">
          <a
            class="feed-repo"
            href=${`https://github.com/${item.repo}`}
            target="_blank"
            rel="noreferrer"
            >${item.repo}</a
          >
          <time datetime=${item.at} title=${date.format(new Date(item.at))}
            >${item.kind === "project" ? `Updated ${when}` : when}</time
          >
          ${item.kind === "project" ? html`<span class="feed-angle">Project to explore</span>` : nothing}
          <span class="feed-angle">${angle}</span>
        </div>
        <h3>
          <a href=${item.url} target="_blank" rel="noreferrer">${item.headline}</a>
        </h3>
        <div class="feed-commentary">
          ${unsafeHTML(renderMarkdown(item.commentary))}
        </div>
        <div class="feed-context" data-distance=${item.distance}>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M2 8h10M8 4l4 4-4 4" />
          </svg>
          <div>${unsafeHTML(renderMarkdown(item.reason))}</div>
        </div>
        <div class="feed-actions">
          <details
            class="feed-source"
            @toggle=${(event) => this.sourceOpened(event, item.id)}
          >
            <summary>
              Source & details
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="m4 6 4 4 4-4" />
              </svg>
            </summary>
            <div class="feed-evidence">
              <p class="feed-source-title">
                <a href=${item.url} target="_blank" rel="noreferrer">${item.title}</a>
              </p>
              <div class="feed-source-meta">
                ${item.author} ·
                ${item.kind === "project" ? "Repository updated " : ""}${date.format(new Date(item.at))}${item.kind === "pull_request" ? html` · +${item.additions} −${item.deletions} · ${item.files} files` : nothing}
              </div>
              <p>
                Retrieval priority: ${item.retrieval_score}.
                ${item.score_components.join(" · ")}. This prioritizes the shortlist; it
                is not an interest prediction.
              </p>
              <div class="feed-markdown">
                ${!this.openedSources.has(item.id) ? nothing : !item.body ? html`<p>No description was included on GitHub.</p>` : markdownReady() ? unsafeHTML(sourceMarkdown(item)) : html`<p>Opening source…</p>`}
              </div>
              <a
                class="feed-source-link"
                href=${item.source_url}
                target="_blank"
                rel="noreferrer"
                >${item.kind === "project" ? "Read the project README" : "Continue on GitHub"}
                <span aria-hidden="true">↗</span></a
              >
            </div>
          </details>
          ${!quoted(this) ? html`<button ${offered("feed-ask")} type="button" title="Ask the agent how this connects to your work" @click=${() => this.ask(item)}>Talk about this</button>` : nothing}
        </div>
      </div>
    </article>`;
  }

  updated() {
    if (!this.shown) return;
    const indices = new Map(this.shown.items.map((item, index) => [item.id, index]));
    // Each story card is a datum on a Leaf page, following its story by id.
    for (const node of this.querySelectorAll("[data-change]")) {
      const index = indices.get(node.dataset.change);
      keeps(node, "data-lf-datum", node.dataset.change);
      keeps(node, "data-lf-identity", node.dataset.change);
      keeps(node, "data-lf-datum-label", this.shown.items[index].headline);
      keeps(node, "data-lf-origin-path", JSON.stringify(["items", index]));
    }
    // A feed live exploration composed came from no source.
    this.dispatchEvent(
      new CustomEvent("drawn", {
        detail: { value: this.shown === this.liveFeed ? null : this.shown },
      }),
    );
    const more = this.querySelector(".feed-more");
    this.observer.disconnect();
    if (more && this.canAdvance) this.observer.observe(more);
  }
}
customElements.define("lf-repo-feed", RepoFeed);
