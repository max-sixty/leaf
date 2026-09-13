"""Stable target identity and hit-testing contracts."""

import pytest
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.nightly


TARGET_PAGE = leaf_page(
    "target references",
    """
    <section id="scope">
      <article id="exact"><p>Exact target</p></article>
      <section id="anonymous-scope">
        <article><h2>First shape</h2></article>
        <article id="neighbor"><p>Different shape</p></article>
      </section>
      <aside id="removal-scope"><div><strong>Removed target</strong></div></aside>
      <div id="hit-scope" style="padding: 24px">
        <section><article><div><span><em><button id="deep">Deep target</button></em></span></div></article></section>
      </div>
    </section>
    """,
)


def test_an_id_resolves_only_when_its_exact_case_is_unique(browser, serve):
    page, errors = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {captureTargetReference, resolveTargetReference} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const root = document.querySelector('#scope');
          const target = document.querySelector('#exact');
          const reference = captureTargetReference(root, target);
          const first = resolveTargetReference(root, reference);
          const wrongCase = resolveTargetReference(root, {...reference, id: 'EXACT'});
          const duplicate = document.createElement('div');
          duplicate.id = 'exact';
          root.append(duplicate);
          const repeated = resolveTargetReference(root, reference);
          return {
            reference,
            first: {status: first.status, same: first.element === target},
            wrongCase: wrongCase.status,
            repeated: repeated.status,
            repeatedHasElement: Object.hasOwn(repeated, 'element'),
          };
        }"""
    )

    assert reading == {
        "reference": {"kind": "id", "id": "exact"},
        "first": {"status": "resolved", "same": True},
        "wrongCase": "detached",
        "repeated": "ambiguous",
        "repeatedHasElement": False,
    }
    assert errors == []
    page.close()


def test_anonymous_structure_never_moves_to_an_inserted_sibling(browser, serve):
    page, errors = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {captureTargetReference, resolveTargetReference} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const root = document.querySelector('#anonymous-scope');
          const target = root.querySelector('article');
          const reference = captureTargetReference(root, target);
          const before = resolveTargetReference(root, reference);
          const inserted = document.createElement('article');
          root.prepend(inserted);
          const afterInsertion = resolveTargetReference(root, reference);
          return {
            kind: reference.kind,
            before: {
              status: before.status,
              same: before.element === target,
            },
            afterInsertion: afterInsertion.status,
            insertionHasElement: Object.hasOwn(afterInsertion, 'element'),
          };
        }"""
    )

    assert reading == {
        "kind": "structure",
        "before": {"status": "resolved", "same": True},
        "afterInsertion": "ambiguous",
        "insertionHasElement": False,
    }
    assert errors == []
    page.close()


def test_removing_an_anonymous_target_detaches_its_reference(browser, serve):
    page, errors = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {captureTargetReference, resolveTargetReference} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const root = document.querySelector('#removal-scope');
          const target = root.querySelector('div');
          const reference = captureTargetReference(root, target);
          target.remove();
          const result = resolveTargetReference(root, reference);
          return {
            status: result.status,
            hasElement: Object.hasOwn(result, 'element'),
          };
        }"""
    )

    assert reading == {"status": "detached", "hasElement": False}
    assert errors == []
    page.close()


def test_pointer_and_keyboard_targets_share_the_unbounded_candidate_walk(
    browser, serve
):
    page, errors = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {targetCandidates} =
            await window.__lfRuntimeImport('/runtime/widget-api.js');
          const root = document.querySelector('#hit-scope');
          const focused = document.querySelector('#deep');
          focused.focus();
          const box = focused.getBoundingClientRect();
          const pointer = targetCandidates(root, {
            x: box.left + box.width / 2,
            y: box.top + box.height / 2,
          });
          const keyboard = targetCandidates(root, document.activeElement);
          const describe = (elements) => elements.map(
            element => element.id || element.localName,
          );
          return {pointer: describe(pointer), keyboard: describe(keyboard)};
        }"""
    )

    assert reading["pointer"] == reading["keyboard"]
    assert reading["pointer"] == [
        "deep",
        "em",
        "span",
        "div",
        "article",
        "section",
        "hit-scope",
    ]
    assert errors == []
    page.close()


def test_a_frozen_fragment_boundary_survives_its_nodes_being_connected(browser, serve):
    page, errors = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {
            captureTargetReference,
            resolveTargetReference,
            targetReferenceBoundary,
          } = await window.__lfRuntimeImport('/runtime/target-references.js');
          const template = document.createElement('template');
          template.innerHTML = '<section id="fragment-anchor"><p>One</p></section>' +
            '<aside><em>Two</em></aside>';
          const paragraph = template.content.querySelector('p');
          const emphasis = template.content.querySelector('em');
          const boundary = targetReferenceBoundary(template.content.children);
          document.querySelector('#scope').append(template.content);
          const anchored = captureTargetReference(boundary, paragraph);
          const unanchored = captureTargetReference(boundary, emphasis);
          return {
            anchored,
            unanchored,
            anchoredStatus: resolveTargetReference(boundary, anchored).status,
            unanchoredStatus: resolveTargetReference(boundary, unanchored).status,
          };
        }"""
    )

    assert reading == {
        "anchored": {
            "kind": "structure",
            "anchor": "fragment-anchor",
            "path": [{"tree": "light", "tag": "p"}],
        },
        "unanchored": {
            "kind": "structure",
            "path": [
                {"tree": "light", "tag": "aside"},
                {"tree": "light", "tag": "em"},
            ],
        },
        "anchoredStatus": "resolved",
        "unanchoredStatus": "resolved",
    }
    assert errors == []
    page.close()
