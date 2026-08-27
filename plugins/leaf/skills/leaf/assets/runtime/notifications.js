let publishedNotifications;
export const announce = (...args) => publishedNotifications.announce(...args);
export const toast = (...args) => publishedNotifications.toast(...args);

export function createNotifications({ liveEl, syncLayout, toastEl }) {
  let toastTimer = 0;

  function announce(msg) {
    liveEl.textContent = "";
    setTimeout(() => (liveEl.textContent = msg), 30);
  }

  function showToast(msg, onClick) {
    announce(msg);
    toastEl.textContent = msg;
    syncLayout();
    toastEl.onclick = onClick || null;
    toastEl.classList.add("show");
    toastEl.classList.toggle("clickable", Boolean(onClick));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove("show", "clickable");
      toastEl.onclick = null;
    }, 4000);
  }

  const notifications = {
    announce,
    showToast,
    toast: (msg) => showToast(msg),
  };
  publishedNotifications = notifications;
  return notifications;
}
