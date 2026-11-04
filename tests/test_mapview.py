# Tests for inlining map points into the HTML page
import json
import re

from suwon_parking.mapview import render
from suwon_parking.points import Point


def test_render_inlines_compact_rows_and_escapes_script_end():
    grid = [0] * 168
    grid[14] = 50
    p = Point(127.0, 37.0, "cctv", "A </script> 앞", "A", "cctv", 3, 0.5, grid)
    html = render([p], "2022-01-01 ~ 2023-10-31", 3)
    assert "/*DATA*/" not in html
    assert "</script> 앞" not in html
    raw = re.search(r"const DATA = (.*);\n", html).group(1)
    data = json.loads(raw.replace("<\\/", "</"))
    assert data["records"] == 3
    assert data["points"][0][3] == "A </script> 앞"
    assert data["points"][0][8] == [[14, 50]]  # only non-zero grid slots
