// Publish a document through Leaf's shared output binding; the reader owns its views.
import { html, LeafElement, publishOutput } from "/runtime/widget-api.js";

customElements.define(
  "lf-document-gallery",
  class extends LeafElement {
    setup() {
      this.edition = 1;
      this.publish();
    }
    publish() {
      publishOutput(
        this,
        "document",
        `# Release note ${this.edition}\n\nThe library opens on **Sunday**.\n`,
      );
    }
    render() {
      return html`<button
        type="button"
        @click=${() => {
          this.edition += 1;
          this.publish();
        }}
      >
        Update document
      </button>`;
    }
  },
);
