# Reads Anyang's per-100 m-grid violation counts (zipped SHP) and attaches them to map points
from __future__ import annotations

import io
import struct
import zipfile

from pyproj import Transformer

from .aggregate import EXACT
from .points import Point

# National grid ids ('다사496357'): two letters name the 100 km square (east, north), then 3 + 3 digits in 100 m.
EAST = {c: 7 + i for i, c in enumerate("가나다라마바사")}
NORTH = {c: 13 + i for i, c in enumerate("가나다라마바사아")}
TO_UTMK = Transformer.from_crs(4326, 5179, always_xy=True)  # Korea 2000 unified (UTM-K) metres


def cell_of(grid_id: str) -> tuple[int, int]:
    """Grid id → (east, north) of the cell's lower-left corner in units of 100 m."""
    return EAST[grid_id[0]] * 1000 + int(grid_id[2:5]), NORTH[grid_id[1]] * 1000 + int(grid_id[5:8])


def _dbf_rows(raw: bytes, encoding: str = "cp949") -> list[dict[str, str]]:
    count, header_len, record_len = struct.unpack("<IHH", raw[4:12])
    fields = [(raw[i:i + 11].split(b"\0")[0].decode(encoding), raw[i + 16]) for i in range(32, header_len - 1, 32)]
    rows = []
    for n in range(count):
        pos = header_len + n * record_len + 1  # skip the deletion flag
        row = {}
        for name, width in fields:
            row[name] = raw[pos:pos + width].decode(encoding).strip()
            pos += width
        rows.append(row)
    return rows


def parse_grid_zip(raw: bytes) -> dict[tuple[int, int], int]:
    """Cell → total violations, from the attribute table (.dbf) inside the published zip."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        # Member names are cp949 bytes that zipfile reads as cp437; only the extension matters here.
        dbf = next(i for i in z.infolist() if i.filename.lower().endswith(".dbf"))
        rows = _dbf_rows(z.read(dbf))
    cells: dict[tuple[int, int], int] = {}
    for r in rows:
        key = cell_of(r["격자ID"])
        cells[key] = cells.get(key, 0) + int(r["단속건수"])
    return cells


def attach_grid(points: list[Point], cells: dict[tuple[int, int], int]) -> None:
    """Set `recent` to the count of the cell containing each exactly located patrol point.

    The grid has no camera enforcement, so camera points are left out, as are rough locations.
    """
    for p in points:
        if p.precision not in EXACT or p.kind == "cctv":
            continue
        x, y = TO_UTMK.transform(p.lon, p.lat)
        p.recent = cells.get((int(x // 100), int(y // 100)), 0)
