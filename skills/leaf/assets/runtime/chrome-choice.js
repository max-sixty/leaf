/* The reader's choice of chrome, as a row in whichever chrome they have: the Leaf panel
 * (`floating`, the default) or the banner and bottom bar (`classic`). The choice is one
 * preference for every page on the origin (prepaint.js, `lfChrome`), and the runtime
 * builds one chrome at boot, so switching stores the other and reloads the page. A
 * sample takes its chrome from its containing page on every load, so it offers no
 * switch. */
import { pageCommand } from "./keyboard/register.js";

const root = document.documentElement;
const floating = () => root.lfChrome.mode === "floating";

if (!root.lfSample)
  pageCommand({
    id: "chrome.switch",
    keys: [],
    title: () => (floating() ? "use the banner" : "use the Leaf panel"),
    description: () =>
      floating()
        ? "Read every page with the banner and bottom bar in place of the Leaf panel"
        : "Read every page with the Leaf panel in place of the banner and bottom bar",
    touch: () => (floating() ? "Use the banner" : "Use the Leaf panel"),
    menu: "page",
    run: () => {
      root.lfChrome.set("mode", floating() ? "classic" : "floating");
      location.reload();
    },
  });
