"""Obtém metadados do ZIP público do ICWSM sem baixar todas as imagens."""

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

URL = "https://zenodo.org/records/3779157/files/icwsm_dataset_share.zip?download=1"
SIZE = 302506953


class RemoteZip(io.RawIOBase):
    def __init__(self):
        self.position = 0

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else (self.position if whence == 1 else SIZE) + offset
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        size = SIZE - self.position if size < 0 else min(size, SIZE - self.position)
        if size <= 0:
            return b""
        end = self.position + size - 1
        request = Request(URL, headers={"Range": f"bytes={self.position}-{end}"})
        with urlopen(request, timeout=60) as response:
            expected = f"bytes {self.position}-{end}/{SIZE}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise ValueError("Servidor não forneceu o intervalo esperado do arquivo fixado.")
            data = response.read()
        if len(data) != size:
            raise ValueError("Download incompleto.")
        self.position += size
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--member", action="append", default=[])
    args = parser.parse_args()
    with ZipFile(RemoteZip()) as archive:
        candidates = [info for info in archive.infolist() if not info.is_dir()
                      and Path(info.filename).suffix.lower() in {".csv", ".txt", ".json", ".md"}]
        if not args.member:
            print(json.dumps([{"member": i.filename, "bytes": i.file_size} for i in candidates], indent=2))
            return
        entries = []
        args.output.mkdir(parents=True, exist_ok=True)
        for member in args.member:
            info = archive.getinfo(member)
            raw = archive.read(info)
            target = args.output / Path(member).name
            if target.exists() and target.read_bytes() != raw:
                raise ValueError(f"Arquivo local diferente: {target}")
            target.write_bytes(raw)
            entries.append({"member": member, "file": target.name, "bytes": len(raw),
                            "sha256": sha256(raw).hexdigest(), "zip_crc32": info.CRC})
        manifest = {"url": URL, "doi": "10.5281/zenodo.3779157", "archive_bytes": SIZE,
                    "verification": "CRC32 de cada membro pelo ZipFile e SHA256 do conteúdo; ZIP completo não baixado",
                    "files": entries}
        (args.output / "source_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
