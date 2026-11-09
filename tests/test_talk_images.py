"""Images attached to a talk: re-encoded small, kept as image lines."""

import io

from PIL import Image

from src.api.talks import _line, _prepare_image


def test_prepare_image_shrinks_and_reencodes():
    big = Image.new("RGB", (4000, 3000), (200, 30, 30))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    data, mime, w, h = _prepare_image(buf.getvalue())
    assert mime == "image/jpeg" and (w, h) == (1600, 1200)
    assert len(data) < 400_000
    alpha = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    buf = io.BytesIO()
    alpha.save(buf, format="PNG")
    data, mime, w, h = _prepare_image(buf.getvalue())
    assert mime == "image/png" and (w, h) == (300, 200)


def test_image_line_keeps_its_fields_and_text_line_does_not():
    img = _line({"kind": "image", "image_id": "abc", "caption": "Noah's ark", "source": "image", "confirmed": True})
    assert img["kind"] == "image" and img["image_id"] == "abc" and img["caption"] == "Noah's ark"
    text = _line({"chk": "Jiowa a tongei aramas", "en": "Jehovah loves people", "kind": "image"})
    assert "kind" not in text and "image_id" not in text
