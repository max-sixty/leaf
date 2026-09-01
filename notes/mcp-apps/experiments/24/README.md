# Experiment 24: Full-page accessibility and return path

## Purpose

Complete the successful full-page run while recording, rather than rejecting,
the reference host's post-fullscreen display-control state.

**Changes from experiment 23:**

- After requesting fullscreen, record the button's hidden/text state and the
  resulting page dimensions without requiring `Return inline` to be visible.
- Continue to Axe and the keyboard choice.
- Change no Leaf implementation, resource, cookie, fixture, or interaction.

**Expected outcomes:**

- Inline and fullscreen dimensions confirm the layout transition.
- Axe finds no serious surface regression and the console contains no Leaf
  failures.
- Choosing Redis from the nested iframe appends an ordinary `choose` action to
  the page's durable event log.

## Findings

Inline Leaf measured 1060×332 with a 2,857px document, no horizontal overflow,
all five representative widgets present, and runtime presentation complete.
The run then called `evaluate` through the wrong Playwright frame-locator API
while reading the now-hidden fullscreen button. Experiment 25 uses the same
role locator that successfully clicked the button, then continues unchanged.
