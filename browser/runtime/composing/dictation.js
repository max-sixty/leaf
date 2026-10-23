/* Native speech recognition for one composition session. The composer owns its words
 * and presentation; this owner writes the recognizer's current reading until editing,
 * sending, closing or replacing that draft retires it. Stop accepts the browser's last
 * result, whereas cancel retires the recognizer before aborting it, so late callbacks
 * cannot refill a sent box or overwrite a user's edit. Only one box captures at a time.
 * This module is loaded on the first microphone press, outside page startup. */

const FAILURES = {
  "not-allowed": "Microphone access blocked",
  "service-not-allowed": "Dictation is off in this browser",
  "audio-capture": "No microphone found",
  network: "Speech service unreachable",
  "language-not-supported": "Language not supported for dictation",
  "no-speech": "No speech heard",
};
const STATUS = {
  starting: "Starting microphone…",
  listening: "Listening…",
  stopping: "Finishing…",
};
let active = null;

export function createDictation({
  Recognition,
  language,
  read,
  write,
  changed,
  announce,
}) {
  let session = null;
  let phase = "idle";
  let failure = null;
  let writing = false;

  const end = (news) => {
    const previous = session;
    session = null;
    phase = "idle";
    if (active === controller) active = null;
    changed();
    if (news) announce(news);
    return previous;
  };
  const cancel = () => {
    if (!session && phase === "idle" && !failure) return;
    failure = null;
    const previous = end();
    previous?.abort();
  };
  const controller = {
    get phase() {
      return phase;
    },
    get failure() {
      return failure;
    },
    get status() {
      return STATUS[phase] ?? failure?.text ?? "";
    },
    cancel,
    edited() {
      if (writing) return;
      const wasActive = session !== null;
      cancel();
      if (wasActive) announce("Dictation stopped");
    },
    stop() {
      if (!session || phase === "stopping") return;
      phase = "stopping";
      changed();
      session.stop();
    },
    start() {
      if (phase !== "idle") return;
      active?.cancel();
      active = controller;
      failure = null;
      const base = read().trim();
      phase = "starting";
      changed();
      try {
        const recognizer = new Recognition();
        session = recognizer;
        recognizer.continuous = true;
        recognizer.interimResults = true;
        recognizer.lang = language;
        recognizer.onstart = () => {
          if (session !== recognizer || phase !== "starting") return;
          phase = "listening";
          changed();
          announce("Listening");
        };
        recognizer.onresult = (event) => {
          if (session !== recognizer) return;
          // Results contains the session's final and interim words together. Replacing
          // that reading, rather than appending each event, never duplicates a final.
          const heard = Array.from(event.results, (result) => result[0].transcript)
            .join(" ")
            .replace(/\s+/g, " ")
            .trim();
          const words = [base, heard].filter(Boolean).join(" ");
          if (read() !== words) {
            writing = true;
            try {
              write(words);
            } finally {
              writing = false;
            }
          }
        };
        recognizer.onerror = (event) => {
          if (session !== recognizer) return;
          const text = FAILURES[event.error] ?? "Dictation stopped";
          if (!read().trim() && event.error !== "aborted")
            failure = { error: event.error, text };
          end(text);
        };
        recognizer.onend = () => {
          if (session === recognizer) end("Dictation stopped");
        };
        recognizer.start();
      } catch {
        failure = { error: "start", text: "Dictation couldn’t start" };
        end(failure.text);
      }
    },
  };
  return controller;
}
