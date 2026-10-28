"""Deterministic downloadable archives of a verified explicitly selected bundle."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED

from .errors import UserError
from .jsonio import canonical, read_bytes, sha256, write_bytes
from .suite import verify_bundle


def write_archive(bundle: Path, destination: Path):
    manifest = verify_bundle(bundle)
    if destination.resolve() == bundle.resolve() or bundle.resolve() in destination.resolve().parents:
        raise UserError("output_inside_bundle")
    payload = {"bundle.json": canonical(manifest) + b"\n"}
    for task in manifest["tasks"]:
        for file in task["files"]:
            path = f"tasks/{task['id']}/{file['path']}"
            data = read_bytes(bundle / path, 1024 * 1024)
            if sha256(data) != file["sha256"] or len(data) != file["bytes"]:
                raise UserError("bundle_changed")
            payload[path] = data
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        for path, data in sorted(payload.items()):
            info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, data)
    data = buffer.getvalue()
    write_bytes(destination, data)
    return {"bundleId": manifest["bundleId"], "bytes": len(data), "sha256": sha256(data)}
