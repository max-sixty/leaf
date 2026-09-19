"""Target-reference contracts that the public product routes cannot isolate."""

import pytest
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.nightly


TARGET_PAGE = leaf_page(
    "target references",
    '<section id="scope"><article id="exact">Exact target</article></section>',
)


def test_target_references_keep_exact_identity_across_document_boundaries(
    browser, serve
):
    page = open_page(browser, serve(TARGET_PAGE))
    reading = page.evaluate(
        """async () => {
          const {
            captureTargetReference,
            resolveTargetReference,
            targetReferenceBoundary,
          } = await window.__lfRuntimeImport('/runtime/target-references.js');

          const root = document.querySelector('#scope');
          const target = document.querySelector('#exact');
          const reference = captureTargetReference(root, target);
          const first = resolveTargetReference(root, reference);
          const wrongCase = resolveTargetReference(root, {...reference, id: 'EXACT'});
          const duplicate = document.createElement('div');
          duplicate.id = 'exact';
          root.append(duplicate);
          const repeated = resolveTargetReference(root, reference);

          const template = document.createElement('template');
          template.innerHTML = '<section id="fragment-anchor"><p>One</p></section>' +
            '<aside><em>Two</em></aside>';
          const paragraph = template.content.querySelector('p');
          const emphasis = template.content.querySelector('em');
          const boundary = targetReferenceBoundary(template.content.children);
          root.append(template.content);
          const anchored = captureTargetReference(boundary, paragraph);
          const unanchored = captureTargetReference(boundary, emphasis);

          return {
            id: {
              reference,
              first: {status: first.status, same: first.element === target},
              wrongCase: wrongCase.status,
              repeated: repeated.status,
              repeatedHasElement: Object.hasOwn(repeated, 'element'),
            },
            fragment: {
              anchored,
              unanchored,
              anchoredStatus: resolveTargetReference(boundary, anchored).status,
              unanchoredStatus: resolveTargetReference(boundary, unanchored).status,
            },
          };
        }"""
    )

    assert reading == {
        "id": {
            "reference": {"kind": "id", "id": "exact"},
            "first": {"status": "resolved", "same": True},
            "wrongCase": "detached",
            "repeated": "ambiguous",
            "repeatedHasElement": False,
        },
        "fragment": {
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
        },
    }
