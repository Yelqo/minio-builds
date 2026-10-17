# Attribution and packaging changes

This is an unofficial MinIO Community Edition build independently published by
Yelqo. Yelqo is not MinIO, Inc. and does not claim upstream maintenance or
security support. MinIO names and marks identify the upstream components.

MinIO server and mc are Copyright MinIO, Inc. and their respective contributors,
licensed under GNU AGPL version 3 or later. Their unmodified LICENSE files are
installed at `/usr/share/licenses/minio/LICENSE` and
`/usr/share/licenses/mc/LICENSE`. The complete source trees, copyright headers,
CREDITS and third-party licenses accompany every release in
`corresponding-source.tar.gz`, including vendored Go dependency sources and
their notices. `go.mod`, `go.sum` and `vendor/modules.txt` identify dependencies.
The base distribution retains its Debian package copyright information.

Packaging changes: source compilation with the pinned Go toolchain; explicit
upstream version/commit linker flags; a pinned Debian runtime; bundled mc;
local mc alias initialization; independent OCI publisher metadata; and
source/SBOM/provenance release evidence. No server or client Go source patches
are applied. The recipe and scripts in this repository are AGPL-3.0-or-later.

The corresponding-source archive contains `src/minio`, `src/mc` (both with
vendor directories), the original checked source archives under `archives`,
`inputs.env`, and the complete build recipe under `recipe`. It is distributed
beside the image digest at https://github.com/Yelqo/minio-builds/releases.
