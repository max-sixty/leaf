"""The probe records real Leaf and ordinary web journeys, including failures."""

from leaf_dev.recording import write_gif
from PIL import Image


def test_gif_retains_the_viewport_when_startup_frame_dimensions_change(tmp_path):
    output = tmp_path / "startup.gif"
    write_gif(
        [Image.new("RGB", (390, 338), "white"), Image.new("RGB", (390, 520), "red")],
        [100, 200],
        output,
    )
    with Image.open(output) as gif:
        assert gif.size == (390, 520)
        gif.seek(1)
        assert gif.convert("RGB").getpixel((389, 519)) == (255, 0, 0)
