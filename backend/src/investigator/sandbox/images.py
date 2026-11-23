"""Build the sandbox images:  python -m investigator.sandbox.images  [python|dotnet|node ...]

All images come from the single sandbox-images/Dockerfile; each adapter supplies its base image
and setup step. On Windows, the host's trusted root certificates are copied into the images so
that dependency downloads also work behind an HTTPS-inspecting filter (e.g. NetFree).
"""

from __future__ import annotations

import ssl
import subprocess
import sys
from pathlib import Path

from ..config import ROOT_DIR
from ..runtimes.adapters import ADAPTERS
from ..runtimes.base import RuntimeAdapter

IMAGES_DIR = ROOT_DIR / "sandbox-images"
HOST_CERTS = IMAGES_DIR / "certs" / "host-roots.crt"


def export_host_certificates(dest: Path = HOST_CERTS) -> int:
    """Write the Windows trusted root/intermediate certificates as one PEM bundle. Returns the count."""
    if sys.platform != "win32":
        return 0
    pems = sorted({ssl.DER_cert_to_PEM_cert(der) for store in ("ROOT", "CA")
                   for der, encoding, _trust in ssl.enum_certificates(store) if encoding == "x509_asn"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(pems), encoding="ascii")
    return len(pems)


def build_image(adapter: RuntimeAdapter) -> None:
    subprocess.run(
        ["docker", "build", "-t", adapter.image,
         "--build-arg", f"BASE_IMAGE={adapter.base_image}",
         "--build-arg", f"SETUP={adapter.image_setup}",
         str(IMAGES_DIR)],
        check=True,
    )


def main(names: list[str]) -> int:
    print(f"Exported {export_host_certificates()} host certificates")
    for adapter in ADAPTERS:
        if not names or adapter.name in names:
            print(f"\n=== building {adapter.image} from {adapter.base_image} ===", flush=True)
            build_image(adapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
