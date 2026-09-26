/* One collapse class, stated outright and spelled to the same set passages.py's
   COLLAPSE_CHARS enumerates: JS's \s and Python's str.isspace() disagree at the edges —
   U+FEFF is whitespace to JS alone, U+0085 and U+001C–001F to Python alone — and a page
   carrying one of those in prose read differently on the two sides, so a `leaf thread
   open` quote could be written against text this runtime never produces. (trim()
   removes exactly this class, so it needs no twin.)

   The passage reader and the pure projection fold both collapse with it, which is why
   it is a module of its own: the fold imports nothing that reaches the DOM. */
export const COLLAPSE =
  /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;
