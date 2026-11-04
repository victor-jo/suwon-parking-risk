# Downloads data.go.kr file datasets used by this project
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

PORTAL = "https://www.data.go.kr"


@dataclass(frozen=True, slots=True)
class Source:
    pk: str
    detail_pk: str
    filename: str


SOURCES = {
    # 2022-01 ~ 2023-10, ~795k enforcement records with time, place text and method.
    "enforcement": Source("15125266", "uddi:f75715d1-4737-4b56-ba4a-b62828189a24", "enforcement_2022_2023.csv"),
    # 534 fixed enforcement cameras with lat/lon; ground truth for checking geocoded camera spots.
    "cctv": Source("15157315", "uddi:9755ad4b-0de3-4983-b080-fd24350d26b9", "fixed_cctv.csv"),
    # 2021 ~ 2025 enforcement records limited to designated zones; same columns as "enforcement".
    # September 2025 citizen reports that led to a fine; date only, no time of day.
    "fines": Source("15155622", "uddi:cf25fa55-674e-45b6-9fa1-f5b892a0339d", "fines_2025_09.csv"),
    "zones": Source("15159231", "uddi:7734401d-79af-40ff-8abd-b5524b4d4c4a", "zone_enforcement_2021_2025.csv"),
}


def download(source: Source, dest_dir: Path, client: httpx.Client | None = None) -> Path:
    """Resolve the dataset's current attachment id, then save the file under dest_dir."""
    own = client is None
    client = client or httpx.Client(timeout=300, follow_redirects=True)
    try:
        info = client.post(
            f"{PORTAL}/tcs/dss/selectFileDataDownload.do",
            data={
                "publicDataPk": source.pk,
                "publicDataDetailPk": source.detail_pk,
                "atchFileId": "",
                "fileDetailSn": "1",
                "publicDataTyCode": "PR0051",
            },
        )
        info.raise_for_status()
        body = info.json()
        if not body.get("status"):
            raise RuntimeError(f"download info request failed for {source.pk}: {body.get('error')}")
        resp = client.get(
            f"{PORTAL}/cmm/cmm/fileDownload.do",
            params={"atchFileId": body["atchFileId"], "fileDetailSn": body["fileDetailSn"]},
        )
        resp.raise_for_status()
        dest = dest_dir / source.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return dest
    finally:
        if own:
            client.close()
