from PIL import Image

from homeframe.frame.pack import FRAME_BYTES, PANEL_HEIGHT, PANEL_WIDTH, pack_image


def blank(value=255):
    return Image.new("L", (PANEL_WIDTH, PANEL_HEIGHT), value)


def test_white_is_set_bits():
    assert pack_image(blank(), 160, False).frame == b"\xff" * FRAME_BYTES


def test_msb_is_the_leftmost_pixel():
    image = blank()
    image.putpixel((0, 0), 0)  # first bit of the first byte
    image.putpixel((9, 1), 0)  # second bit of the second byte of row 1
    frame = pack_image(image, 160, False).frame
    assert frame[0] == 0x7F
    assert frame[PANEL_WIDTH // 8 + 1] == 0xBF
    assert frame.count(b"\xff") == FRAME_BYTES - 2


def test_threshold_is_inclusive_white():
    assert pack_image(blank(160), 160, False).frame[0] == 0xFF
    assert pack_image(blank(159), 160, False).frame[0] == 0x00


def test_dither_keeps_paper_clean_and_mixes_midtones():
    assert pack_image(blank(), 160, True).frame == b"\xff" * FRAME_BYTES
    black = sum(bin(b ^ 0xFF).count("1") for b in pack_image(blank(128), 160, True).frame)
    assert 0.4 < black / (PANEL_WIDTH * PANEL_HEIGHT) < 0.6


def test_etag_follows_the_pixels():
    image = blank()
    first = pack_image(image, 160, False).etag
    assert first == pack_image(blank(), 160, False).etag
    image.putpixel((5, 5), 0)
    assert first != pack_image(image, 160, False).etag
