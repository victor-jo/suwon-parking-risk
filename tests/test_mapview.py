# Tests for inlining map points into the HTML page
import json
import re

from suwon_parking.mapview import CityLayer, render
from suwon_parking.points import Point


def _data(html: str) -> dict:
    raw = re.search(r"const DATA = (.*);\n", html).group(1)
    return json.loads(raw.replace("<\\/", "</"))


def test_render_inlines_compact_rows_and_escapes_script_end():
    grid = [0] * 168
    grid[14] = 50
    p = Point(127.0, 37.0, "cctv", "A </script> 앞", "A", "cctv", 3, 0.5, grid, recent=4)
    html = render([CityLayer("수원", "2022-01-01 ~ 2023-10-31", 3, [p], hours=True, recent=True)])
    assert "/*DATA*/" not in html
    assert "</script> 앞" not in html
    data = _data(html)
    assert data["cities"] == [{"name": "수원", "period": "2022-01-01 ~ 2023-10-31", "records": 3, "hours": True, "recent": True,
                               "reportsOnly": False}]
    assert data["points"][0][3] == "A </script> 앞"
    assert data["points"][0][8] == [[14, 50]]  # only non-zero grid slots
    assert data["points"][0][9] == 4
    assert data["points"][0][10] == 0  # city index


def test_render_tags_each_point_with_its_city():
    a = Point(127.0, 37.2, "address", "a", "a", "patrol", 1, 0.1, [0] * 168)
    b = Point(127.1, 37.4, "address", "b", "b", "cctv", 1, 0.1, [0] * 168)
    data = _data(render([CityLayer("수원", "p1", 1, [a], hours=True, recent=True),
                         CityLayer("성남", "p2", 1, [b], hours=False, recent=False)]))
    assert [(r[3], r[10]) for r in data["points"]] == [("a", 0), ("b", 1)]
    assert data["cities"][1]["hours"] is False


def test_render_marks_report_only_cities():
    a = Point(127.0, 37.4, "address", "a", "a", "patrol", 1, 0.1, [0] * 168)
    data = _data(render([CityLayer("과천", "p", 1, [a], hours=False, recent=False, reports_only=True)]))
    assert data["cities"][0]["reportsOnly"] is True
