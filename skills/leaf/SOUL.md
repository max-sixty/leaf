# Leaf

Leaf gives a user an interface shaped around their work with an agent. The agent
makes the work visible; the user reads, explores, points at exact passages, and
acts; the agent responds by revising the page. Leaf provides the shared
capabilities that make this exchange reliable and familiar across tasks, pages,
and agents.

**The user directs the work.** The agent authors the page’s content and
presentation, and the user’s instructions and preferences take precedence over
both. Responsiveness to the user takes priority over the agent’s work in
progress. Leaf’s defaults guide choices the user and author have left open.
Editorial judgment belongs with them; Leaf supplies the guarantees they can rely
on.

**Make the work concrete and playable.** Put the subject of a judgment in front
of the user: an interface to inspect, a behavior to try, a proposal drawn, or
the exact words to consider. Each view makes its purpose and available actions
apparent. An action whose result the page can draw shows that result at once.
Words explain the claim, reason, and cost that the presentation cannot show.

**Let the user work as directly as in a terminal.** Keep the page focused on
engaging with the work. Every result a pointer reaches can also be reached by
keyboard, and Leaf’s keys work the same on every page. Aim for a minimal,
elegant interface with simple layouts and a clear visual hierarchy, where Leaf’s
own controls are few, recognizable, and visually secondary to the work. The
resemblance to a terminal lies in how the user works, not in how the page looks.
A page uses anything a browser can show or accept, such as typography, images,
diagrams, charts, and pointer and touch input, where it helps the user
understand the work or act on it.

**Primitives, not a template.** An author who writes good HTML and CSS gets the
page they wrote. Leaf adds what a page can't do alone: comments on exact
passages, recorded choices, live revisions, and the panel and threads that carry
them. Its look and its widgets are defaults a page may take, not a frame every
page must wear. Leaf reaches into the author's markup, styles and scripts only to
keep a guarantee the user relies on, and says so where the author will see it.

**Keep the page current and the record trustworthy.** A returning user can see
where the work stands and what needs their attention. Finished work reduces to
its outcome. Controls mean what they say, and the record preserves what the user
decided, even as the page changes. User edits and choices remain effective until
explicitly changed or withdrawn. Promised work remains owed until it is
fulfilled or explicitly ended with a reason.

**Preserve the user’s attention and work.** Live revisions let the user keep
reading, aiming, and writing. Incoming updates preserve their reading position
and the controls they are using. Typed words and the editing position survive
changes around them. Changes the user requests remain understandable as they
happen. Speed serves the user when the page also keeps them oriented.

**Keep the foundation small and extensible.** Leaf has a small core and default
packages. Authors can compose pages, create widgets, and share packages;
independent packages use the same declared interfaces as the defaults. Shared
capabilities provide difficult behavior, consistent interaction, and
presentation craft that authors would otherwise rebuild. Each mechanism must
justify its continuing cost through the user benefit it provides. Simplification
should remove machinery while preserving the freedom to compose capabilities
beyond the bundled defaults.
