// runtime/chrome.js
var chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
var chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");

export {
  chromeRoot,
  chromeForeground
};
