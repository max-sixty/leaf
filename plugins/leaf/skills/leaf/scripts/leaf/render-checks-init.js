addEventListener("error", (event) => {
  if (!event.error) console.error(`window error: ${event.message}`);
});
