from app.services.ocr import _text_from_data


def test_text_from_data_preserves_line_breaks_and_reading_order():
    # Mirrors the real shape of pytesseract.image_to_data(output_type=DICT):
    # a row per detected element at every level (page/block/paragraph/line/
    # word), not just words - non-word rows carry an empty "text" and a -1
    # "conf", which the confidence averaging elsewhere already relies on.
    data = {
        "block_num": [0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3],
        "par_num": [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1],
        "line_num": [0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1],
        "text": ["", "", "", "", "Hello", "world", "", "Second", "line", "here.", "", "", "", "Third", "para"],
        "conf": [-1, -1, -1, -1, 96.0, 94.5, -1, 91.0, 88.0, 90.2, -1, -1, -1, 93.0, 95.0],
    }

    assert _text_from_data(data) == "Hello world\nSecond line here.\nThird para"


def test_text_from_data_on_a_blank_page():
    data = {"block_num": [0], "par_num": [0], "line_num": [0], "text": [""], "conf": [-1]}

    assert _text_from_data(data) == ""
