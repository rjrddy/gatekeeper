"""Pinned official scanner archives; verify SHA256 before extracting just the binary."""

import hashlib
import platform
import subprocess
import tarfile
from pathlib import Path

cache = Path(".cache/tools")
cache.mkdir(parents=True, exist_ok=True)
bin_dir = Path(".cache/bin")
bin_dir.mkdir(parents=True, exist_ok=True)
system = "darwin" if platform.system() == "Darwin" else "linux"
arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "amd64"
for name, version in [("syft", "1.55.0"), ("grype", "0.121.0")]:
    archive = f"{name}_{version}_{system}_{arch}.tar.gz"
    checksums = f"{name}_{version}_checksums.txt"
    for asset in (archive, checksums):
        if not (cache / asset).exists():
            subprocess.run(
                [
                    "gh",
                    "release",
                    "download",
                    "v" + version,
                    "--repo",
                    "anchore/" + name,
                    "--pattern",
                    asset,
                    "--dir",
                    str(cache),
                ],
                check=True,
            )
    expected = next(
        line.split()[0]
        for line in (cache / checksums).read_text().splitlines()
        if line.split()[-1].lstrip("*") == archive
    )
    if hashlib.sha256((cache / archive).read_bytes()).hexdigest() != expected:
        raise ValueError("scanner archive checksum mismatch")
    with tarfile.open(cache / archive) as tar:
        source = tar.extractfile(name)
        if source is None:
            raise ValueError("scanner missing from archive")
        target = bin_dir / name
        # Never overwrite the source repository if a development symlink exists.
        if target.is_symlink():
            target.unlink()
        target.write_bytes(source.read())
        target.chmod(0o755)
print("Pinned Syft and Grype ready; public HTTPS release manifest verified.")
