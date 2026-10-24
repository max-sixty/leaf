//#region runtime/chrome.js
const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
const chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");

//#endregion
export { chromeForeground, chromeRoot };