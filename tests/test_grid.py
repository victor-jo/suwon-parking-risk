# Tests for reading Anyang's 100 m grid counts and attaching them to map points
import io
import struct
import zipfile

from suwon_parking.grid import attach_grid, cell_of, parse_grid_zip
from suwon_parking.points import Point


def _dbf(rows: list[dict[str, str]], widths: dict[str, int]) -> bytes:
    head = b"".join(k.encode("cp949").ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([w]) + b"\0" * 15 for k, w in widths.items())
    rlen = 1 + sum(widths.values())
    out = struct.pack("<BBBBIHH20x", 3, 126, 1, 1, len(rows), 32 + len(head) + 1, rlen) + head + b"\r"
    for r in rows:
        out += b" " + b"".join(r[k].encode("cp949").ljust(w) for k, w in widths.items())
    return out + b"\x1a"


def _zip(dbf: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("격자.dbf".encode("cp949").decode("cp437"), dbf)  # names are cp949, as published
        z.writestr("x.shp", b"")
    return buf.getvalue()


def test_cell_of_reads_national_grid_ids():
    # '다사496357' is the 100 m square whose lower-left corner is (949600, 1935700) in EPSG:5179.
    assert cell_of("다사496357") == (9496, 19357)


def test_parse_grid_zip_sums_counts_per_cell():
    widths = {"격자ID": 10, "단속건수": 5}
    raw = _zip(_dbf([{"격자ID": "다사496357", "단속건수": "9"}, {"격자ID": "다사527325", "단속건수": "3"},
                     {"격자ID": "다사496357", "단속건수": "6"}], widths))
    assert parse_grid_zip(raw) == {(9496, 19357): 15, (9527, 19325): 3}


def test_attach_grid_sets_count_of_containing_cell_for_exact_patrol_points_only():
    # (126.93098, 37.41952) is the centre of cell 다사496357.
    def pt(prec, kind):
        return Point(126.93098, 37.41952, prec, "p", "p", kind, 1, 0.1, [0] * 168)

    exact, rough, camera = pt("address", "patrol"), pt("dong", "patrol"), pt("landmark", "cctv")
    attach_grid([exact, rough, camera], {(9496, 19357): 15})
    assert (exact.recent, rough.recent, camera.recent) == (15, 0, 0)
