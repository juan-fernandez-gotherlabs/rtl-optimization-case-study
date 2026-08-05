"""Create a deterministic CycloneDX inventory from the pinned image manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote


def _component(ecosystem: str, name: str, version: str) -> dict[str, object]:
    encoded_name = quote(name, safe="._-")
    encoded_version = quote(version, safe="._-+~:")
    purl_type = "deb" if ecosystem == "ubuntu" else "pypi"
    purl = f"pkg:{purl_type}/{encoded_name}@{encoded_version}"
    return {
        "type": "library",
        "bom-ref": purl,
        "name": name,
        "version": version,
        "purl": purl,
        "properties": [{"name": "evolther:package-ecosystem", "value": ecosystem}],
    }


def generate_sbom(
    dpkg_manifest: Path, pip_manifest: Path, output: Path
) -> dict[str, object]:
    """Write a deterministic CycloneDX 1.5 JSON software inventory."""
    components: list[dict[str, object]] = []
    for line in dpkg_manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, version = line.split("\t", 1)
        components.append(_component("ubuntu", name, version))
    for line in pip_manifest.read_text(encoding="utf-8").splitlines():
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        components.append(_component("python", name, version))
    components.sort(key=lambda item: str(item["bom-ref"]))
    fingerprint = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload: dict[str, object] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{fingerprint[:8]}-{fingerprint[8:12]}-{fingerprint[12:16]}-"
        f"{fingerprint[16:20]}-{fingerprint[20:32]}",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "evolther-vtr-ppa45-image"}
        },
        "components": components,
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
