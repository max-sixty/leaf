# Keyboard command and binding ownership

Status: implemented

## Goal

Leaf needs one keyboard model that remains predictable as independently authored
packages add and nest widgets. The model must preserve native editing, let focused
widgets provide compact local operation, and keep contextual surfaces such as Ask from
copying widget behavior.

The resulting model has three parts:

- Commands belong to the layer that implements their semantic result.
- Bindings are routes to commands, not command identity.
- A key resolves through focused semantic ancestry, from the nearest declaration out.

## Terms

**Command** is a stable capability in the keyboard register. Its owner supplies its id,
words, liveness, control, and implementation. A command may have no intrinsic keyboard
binding and remain executable from a visible control or a contextual route.

**Binding** is one route from a key press to a command. A widget binding is intrinsic to
that widget's focus scope. A projection such as Ask may add a contextual binding without
changing the command or its intrinsic routes.

**Scope** is the semantic region in which a set of bindings receives first refusal. An
element scope stands while focus is on that element or within its composed-tree
descendants. Modes and Leaf page behavior contribute scopes through the same resolver.

**Projection** derives a contextual presentation from canonical registrations and
state without becoming a second owner of either. Ask projects registered Decision
commands into contextual routes. Threads similarly projects canonical conversations
into the panel, living margin, and widget-local outlets; it does not project commands.

## Ownership rules

### Commands belong to the layer that implements the result

Leaf owns page reading, chrome, shared commenting, search, navigation, and workspace
commands. A widget owns commands that interpret or change that widget's content. A
widget can expose a control or target to a Leaf command without acquiring the command;
for example, a visual widget supplies a comment target while Leaf owns Comment.

Command identity is stable across its routes. The Swipe widget owns `swipe.pass` whether
the reader invokes it with ArrowLeft inside the deck, with an Ask digit from the question,
or from the complete command reference.

### Focused ancestry resolves bindings

For an ordinary key press, the resolver walks:

1. the exact focused control or active mode;
2. the nearest focused widget scope;
3. ancestor widget scopes;
4. Leaf's contextual and page scopes;
5. the browser.

Within the focused element ancestry, the first scope that declares the binding owns its
Leaf meaning. An element scope receives first refusal only for keys it declares; every
undeclared key continues outward. After that ancestry, Leaf's contextual and page tables
remain peers at one outer level and resolve their first live command. Package load order,
tag names, command-id prefixes, and a global protected-character list do not participate.

A presentation-only row has no `run`. It may name a browser-native press or give a
widget-specific description to a shared outer Leaf handler, but it does not claim Leaf
dispatch and therefore does not shadow that handler. Ownership below refers to a row that
implements a Leaf invocation.

An element declaration retains precedence while its command is unavailable. Liveness
decides whether a command executes and appears in projections, not whether the same key
suddenly acquires an ancestor's different meaning. An unavailable inner declaration
therefore suppresses outer Leaf commands while leaving any browser default intact.

This rule applies equally to character keys, digits, punctuation, named keys, and chords.
Leaf's familiar page grammar remains the outer default: a widget changes a key only while
focus is inside a scope that explicitly declares that key.

### Native interaction stands before ancestor widgets

Native controls retain platform activation, selection, adjustment, editing, and
composition. A text entry's character, deletion, caret, Home/End, and page-movement
claims stand after an exact scope on that control and before any ancestor widget. An
editor can therefore declare Mod+Enter or Escape exactly while retaining ordinary text
entry and preventing an enclosing deck from taking its arrows.

An active mode owns its continuations and inverse. Leaf orders nested Escape behavior
through the return stack; one press unwinds one layer.

### Leaf assigns collection-wide bindings

Some routes are properties of a complete collection rather than any one widget:

- Ask assigns `1` through `9` to the ordered live Decisions in the Ask.
- Go-to assigns generated addresses after reading every visible destination.

Packages contribute commands and controls, not those contextual bindings. Every Ask
Decision consumes one digit while capacity remains, even when the command also has an
intrinsic widget binding. ArrowLeft remains Swipe's local route; `1` is the Ask's
independent route to the same `swipe.pass` command.

An Ask digit remains outer to a focused widget scope. If that widget declares the same
digit, the widget receives it while focused and the Ask route is not advertised. Other
digits continue outward to the Ask. When focus returns to the Ask itself, its complete
digit map is active again.

## Register contract

The register remains the single declaration source. Each scoped command reference
captures the source element, exact registered scope, row, stable command id, intrinsic
invocation argument, and control. Contextual routes retain that reference rather than a
copy of `run`.

Before invocation, dispatch revalidates that:

- the source remains connected and owns the same scope;
- the scope and row are still available;
- the stable id and intrinsic route still exist;
- a runnable implementation or connected native control remains.

Key dispatch, contextual aliases, and command-reference invocation then share the same
execution path. The original row receives the original invocation argument and supplies
the return frame. A digit alias does not pass its digit to a widget command or create a
second click implementation.

Resolved projections use binding reachability, not only command-id reachability. This is
necessary because an intrinsic widget route and an Ask alias deliberately share a command
id while different focus scopes may make only one of their bindings reachable.

## Cases

| Focus and declaration | Press | Result |
| --- | --- | --- |
| Page, no nearer declaration | `c` | Leaf's page Comment command |
| Focused widget declares `c` | `c` | Widget command |
| Focused widget does not declare `c` | `c` | Leaf's page Comment command |
| Focused widget implements dead `c` | `c` | No Leaf command; outer Comment remains suppressed |
| Focused widget only describes an outer route | route | Outer implementation remains reachable |
| Ask itself | `1` | First live Decision through its original command |
| Swipe deck inside Ask | ArrowLeft | Swipe's intrinsic Pass route |
| Widget inside Ask declares `1` | `1` | Widget route; Ask's first route is not advertised |
| Text input inside a widget | character or caret key | Native editing |
| Exact editor scope | Mod+Enter | Editor submission command |
| Nested widgets both declare `]` | `]` | Nearest focused widget command |
| Active Go-to mode | continuation | Go-to mode command |

## Alternatives considered

### Protect Leaf's character namespace globally

This keeps page keys invariant even inside a focused widget, but requires provenance,
collision validation, and exceptions for contextual capabilities. It also prevents useful
focused punctuation and digit interactions even though focus already supplies a clear
boundary. The extra namespace system does not buy enough predictability over ancestry.

### Give every character to Leaf except when a widget is focused

This is close to the chosen model but is too coarse if interpreted as handing the whole
keyboard to the widget. A focused widget must receive only its declared bindings; otherwise
it can silently swallow page commands it does not implement. Declaration-based first
refusal states the seam precisely.

### Let liveness decide ownership

This makes a key fall through to a different semantic action as widget state changes. A
disabled local action could unexpectedly run a page operation, and projections would
shift between meanings without focus moving. Keeping declaration and liveness separate
avoids that instability.

### Copy widget callbacks into Ask

This is mechanically small but creates a second invocation path. It loses command return
frames, can retain replaced controls, and lets key and projection behavior drift. Scoped
command references retain one implementation and validate it at the moment of use.

### Introduce a generic Projection class

Ask and Threads share the rule that a projection derives a contextual presentation
without taking ownership, but not the same inputs or lifecycle. Ask reads commands and
adds routes; Threads reads conversations and chooses panel, margin, or widget outlets. A
generic class would freeze an abstraction before a second identical mechanism exists.
Shared command references and scope resolution provide the keyboard seam without
inventing a superclass.

## Consequences

The model is intentionally permissive: a focused package may shadow a learned Leaf page
key. That behavior is bounded by visible semantic focus and an explicit declaration, and
the key returns to Leaf as soon as focus leaves the widget. If real packages make that
freedom confusing, command metadata can later distinguish application intents from local
operations without replacing the ancestry resolver.

The present design does not add a reader-wide character-shortcut preference. Such a
preference is an orthogonal route filter: it can remove character bindings while leaving
commands and non-character routes intact. It should be added only with its own complete
dispatch, projection, persistence, and accessibility contract.
