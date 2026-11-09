"""The site's product pages as a browser draws them from their sources. The published
build, its routes and its hosting are `journeys/test_site.py`'s."""

from render_harness import open_page, resized

from leaf import render_checks as render_checks_model
from leaf_dev.example_data import named_source


def test_the_data_structures_tables_read_on_a_phone(browser, serve):
    """The data-structures reference's tables, generated from the schemas, read at a
    phone's width: on a narrow column each field's description takes the row's whole
    width under its name, type and flag, so no table scrolls sideways or squeezes a
    cell to a word a line (`squeezedTables`), as 31 of them did with four columns side
    by side. At 640px the column is just wide enough for the four-column table, which
    has to fit there too."""
    page = open_page(browser, serve(named_source("data-structures")))
    for width in (360, 390, 600, 640):
        resized(page, width, 844)
        scrolling = page.evaluate(
            "() => [...document.querySelectorAll('table')]"
            ".filter((table) => table.scrollWidth - table.clientWidth > 1)"
            ".map((table) => table.closest('section').id)"
        )
        squeezed = render_checks_model.evaluate_probe(page, "squeezedTables")
        assert (scrolling, squeezed) == ([], []), f"at {width}px"
    page.close()
