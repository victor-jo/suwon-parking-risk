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
