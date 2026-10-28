"""Read the leaf mark and its focus outline from captured pixels.

Geometry alone misses clipping and compositor paint defects. Both the settled
product check and the opt-in motion benchmark use these colour bounds.
"""

from PIL import Image, ImageChops

from leaf.render_checks import rendered


def settled(page):
    """Wait until layout has started the panel's motion and that motion has finished,
    so a box read is where it rests."""
    rendered(page)
    page.wait_for_function(
        "() => ['.lf-floating-panel', '.lf-fp-ground'].every(s =>"
        " !document.querySelector(s).getAnimations({subtree: true}).some(a =>"
        " Number.isFinite(a.effect?.getComputedTiming().endTime)))"
    )


def ink_box(image, colour):
    difference = ImageChops.difference(image, Image.new("RGB", image.size, colour))
    channels = [
        channel.point(lambda value: 255 if value < 30 else 0)
        for channel in difference.split()
    ]
    return ImageChops.darker(ImageChops.darker(*channels[:2]), channels[2]).getbbox()
