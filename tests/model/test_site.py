"""The published site: what the build assembles, and what a user gets.

The site is the repo's product pages, examples, and developer feature gallery as live
Leaf pages, so most of what could go wrong is a path that meant one thing in a checkout
and another on a host.
The build resolves every local link it wrote and stops on one that reaches
nothing, which is the failure a static host answers with a 404 and no other
signal; these tests hold the rest — that the theme a page links is the shipped
file, that an example served here is a working page rather than a picture of one,
and that a site claiming to ride the theme's tokens actually changes colour when
the theme's palette does.

Every page is reached over HTTP through its page-scoped vendored layer and the canonical
server.
"""

import re

import pytest
from leaf_dev.leaf_assets import pinned_assets, raw_prefix, specification

# The suite's own page primitives, so a navigation here waits on what every other
# navigation waits on. tests/AGENTS.md, "Waits".


# The module-scoped build and host are one shared setup, so they belong to one
# xdist work unit rather than being rebuilt independently on every worker.
pytestmark = [pytest.mark.xdist_group(name="site")]

from journeys.test_site import ROOT


def test_the_readme_draws_its_images_from_the_pinned_assets():
    """GitHub renders the README with no build to fetch into, so its images are raw
    URLs into max-sixty/leaf-assets. Each names the pinned revision, which `publish`
    moves them to, and a file that revision holds."""
    repository, revision = specification()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    images = re.findall(
        rf"{re.escape(raw_prefix(repository))}([0-9a-f]{{40}})/([^\"\s)]+)", readme
    )
    assert images, "the README draws no image from the asset repository"
    assert {pinned for pinned, _ in images} == {revision}
    assets = pinned_assets()
    assert [path for _, path in images if not (assets / path).is_file()] == []
