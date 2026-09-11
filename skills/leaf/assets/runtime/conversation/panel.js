/* The thread panel's general composer and its one draft/drawing authority. */
import { landTyping, mayLandTyping } from "../composing/capture.js";
import { validDrawing } from "../composing/drawing-record.js";
import {
  loadDraft,
  loadDraftPayload,
  mirrorDraft,
  saveDraft,
  sendMessage,
  watchDraft,
} from "../drafts.js";
import { closeBtn, generalInput, generalSend } from "./panel-elements.js";

const drawingIn = (payload) =>
  validDrawing(payload?.drawing) ? payload.drawing : null;

export function createPanelComposer({
  designModeActive,
  wireInput,
  createPageComment,
  showThread,
  setPanel,
  paintDrawings,
}) {
  let sync = () => {};
  let generalDrawing = drawingIn(loadDraftPayload("general"));
  const generalHint = () =>
    designModeActive() && !generalDrawing
      ? "Comment on the layer"
      : "Comment on the page";
  const syncGeneral = () => sync();
  const pageComposerDrawing = () => generalDrawing;

  function saveGeneralDraft(text = sync.value()) {
    return saveDraft(
      "general",
      text,
      generalDrawing ? { drawing: generalDrawing } : undefined,
    );
  }

  function openPageDrawing(drawing) {
    generalDrawing = drawing;
    saveGeneralDraft();
    setPanel(true);
    generalInput.focus({ preventScroll: true });
    sync();
    paintDrawings();
  }

  function mount() {
    closeBtn.onclick = () => setPanel(false);
    generalInput.value = loadDraft("general") ?? "";
    sync = wireInput(generalInput, {
      hint: generalHint,
      accessibleName: generalHint,
      sends: "send",
      sendBtn: generalSend,
      hasContent: (raw) => Boolean(raw || generalDrawing),
      save: saveGeneralDraft,
      send: async (_text, raw, owns) => {
        const sent = await sendMessage("general", owns, (attempt, payload) => {
          const event = { attempt };
          if (raw) event.text = raw;
          const drawing = drawingIn(payload);
          if (designModeActive() && !drawing) event.about = "layer";
          if (drawing) event.drawing = drawing;
          return createPageComment(event);
        });
        if (!sent) return;
        const shouldLand = mayLandTyping(generalInput);
        showThread(sent.id, { focus: false });
        if (shouldLand) landTyping(generalInput);
      },
    });
    sync();
    mirrorDraft(generalInput, sync, "general");
    watchDraft("general", (_value, payload) => {
      generalDrawing = drawingIn(payload);
      sync();
      paintDrawings();
    });
  }

  return {
    generalHint,
    syncGeneral,
    pageComposerDrawing,
    openPageDrawing,
    mount,
  };
}
