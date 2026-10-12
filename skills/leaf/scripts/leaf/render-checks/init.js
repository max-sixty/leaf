addEventListener("error", (event) => {
  if (event.error) return;
  globalThis.__leafWindowError?.({
    text: event.message,
    resizeLoop: event.message.startsWith("ResizeObserver loop"),
  });
});
