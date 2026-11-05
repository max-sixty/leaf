Create the requested page content in one response. Use no tools. Return only
the artifact in the requested encoding, without code fences or explanatory text.
The host provides the document, Leaf runtime, typography, spacing, form behavior
and local server. Write one section root. Do not write JavaScript or CSS.

Both encodings have the following component catalog and behavior:

- Content elements: section, div, h1, h2, h3, p, strong, em, small, span, ul, ol,
  li, dl, dt, dd, br, table, thead, tbody, tr, th, td.
- Leaf decision elements: lf-ask frames a question and may contain a heading,
  evidence and lf-options. Give lf-ask an id. lf-options contains lf-option
  elements. Give the group an id and the boolean choose attribute to enable
  selection. Leave multiple absent for an exclusive choice. Each lf-option
  needs its own unique id and contains the option's visible content. Clicking
  an option records and visibly marks the choice; choosing another replaces it.
  The chosen boolean attribute records an existing decision, so leave it absent
  when the user has not decided. Recommendation is prose, not a chosen value.
  These choices record a local decision and perform no rollout operation.
  In this experiment, lf-ask accepts only id; lf-options accepts id, choose and
  multiple; lf-option accepts id and chosen. Ordinary HTML attributes below do
  not apply to these Leaf elements. Put any labeled section around them.
- Form elements: form, label, input, select, option, textarea, button, fieldset,
  legend, output. Use an input type=text with name=title and accessible label
  "Title", a select name=severity with accessible label "Severity", and a
  textarea name=impact with accessible label "Customer impact". The option
  values are Low, Medium, High. Label by nesting the control inside label or
  by label for referring to the control's id. Use a button type=submit.
  The host intercepts submission of any form, reads all named values, and
  creates or updates an output inside that form showing those values with
  "Draft recorded locally for review". It sends nothing and changes no service.
  Do not prefill the user's title or impact. You may include an initially empty
  output or let the host create it.
- Available attributes on ordinary HTML elements: id, class, title, role,
  aria-label, aria-labelledby, aria-describedby, aria-live, multiple, for, type,
  name, value, required, placeholder, rows, cols, maxlength, minlength, selected,
  checked, disabled, scope. Use only attributes appropriate to the element. All ids
  must be unique; Leaf element ids use lowercase letters, numbers and hyphens.
  The host supplies ordinary browser semantics for HTML elements. input and br
  are void elements with no children. All other elements have closing tags in
  HTML and a children array in JSON. Text is literal, with no Markdown syntax.

Choose a clear, compact organization for the reader's task. Preserve supplied
facts, uncertainties and limits. Use the same component behavior described
above rather than describing an interaction the reader cannot perform.
