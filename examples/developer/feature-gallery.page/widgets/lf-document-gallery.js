// Hold a document as the `document` output and say `change`; the reader that names this
// element owns its views.
import { html, LeafElement } from "/runtime/widget-api.js";

customElements.define(
  "lf-document-gallery",
  class extends LeafElement {
    setup() {
      this.edition = 1;
      this.publish();
    }
    publish() {
      this.document = `# Release note ${this.edition}\n\nThe library opens on **Sunday**.\n`;
      this.dispatchEvent(new Event("change"));
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
