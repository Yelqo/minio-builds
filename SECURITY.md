# Security scope and input decision

Reviewed 2026-10-17 for tsoporto/monorepo#588. This repository owns distribution,
not an actively maintained MinIO server fork. Its images are for isolated,
disposable integration tests with test credentials and no production data.
Publishing an image does not provide upstream security support.

The former compatibility baseline was `RELEASE.2025-09-07T16-13-09Z`.
We select the later official Community Edition security release
`RELEASE.2025-10-15T17-29-55Z`, commit
`9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`, to include the service-account/STS
session-policy fix:
https://github.com/minio/minio/security/advisories/GHSA-jjjj-jwhf-8rgr.
Release details: https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z.
The client is pinned independently to `RELEASE.2025-08-13T08-35-41Z`, commit
`7394ce0dd2a80935aded936b09fa12cbb3cb8096`.

The public server advisory list was reviewed, including advisories published
after the final Community Edition release. These are **not** all fixed by this
source selection:

| Advisory | Remaining scope |
| --- | --- |
| [GHSA-hv4r-mvr4-25vw](https://github.com/minio/minio/security/advisories/GHSA-hv4r-mvr4-25vw) | Unsigned-trailer query-credential signature bypass; affected Community Edition |
| [GHSA-9c4q-hq6p-c237](https://github.com/minio/minio/security/advisories/GHSA-9c4q-hq6p-c237) | Snowball extraction signature bypass; affected Community Edition |
| [GHSA-h749-fxx7-pwpg](https://github.com/minio/minio/security/advisories/GHSA-h749-fxx7-pwpg) | S3 Select CSV allocation denial of service |
| [GHSA-3rh2-v3gr-35p9](https://github.com/minio/minio/security/advisories/GHSA-3rh2-v3gr-35p9) | Replication-header encryption metadata injection |
| [GHSA-xh8f-g2qw-gcm7](https://github.com/minio/minio/security/advisories/GHSA-xh8f-g2qw-gcm7) | ReadMultiple traversal in distributed deployments; standalone mode does not register the route |
| [GHSA-jv87-32hw-hh99](https://github.com/minio/minio/security/advisories/GHSA-jv87-32hw-hh99) | LDAP enumeration/rate limits; upstream names AIStor; test configuration has no LDAP |
| [GHSA-5cx5-wh4m-82fh](https://github.com/minio/minio/security/advisories/GHSA-5cx5-wh4m-82fh) | OIDC algorithm confusion; upstream names AIStor; test configuration has no OIDC |

Later patched AIStor versions named in advisories are not Community Edition
source releases. No assumption is made that selecting the final open-source
release includes proprietary fixes. No private patches, Silo source changes,
or security-support claims are included. Test networks must remain isolated
from untrusted users. Successful normal S3/policy tests are compatibility
evidence, not proof that authentication bypasses are absent.

The upstream client advisory API returned no published advisories at review
time; that is not a claim of no vulnerabilities. Each input upgrade requires
another advisory review and both producer and consumer qualification.

Prior art reviewed: https://github.com/coollabsio/minio for source builds and
https://github.com/pgsty/silo for release evidence. This recipe is independent;
it does not select moving upstream inputs or adopt the Silo server fork.

## Distribution maintenance, 2026-11-03

The [2026-11-02 maintenance run](https://github.com/Yelqo/minio-builds/actions/runs/41454355884)
scanned the consumed `v0.1.0` digest on both architectures with a fresh database.
Each architecture reported 68 fixable High/Critical package findings (17 Critical,
51 High; 53 distinct advisory IDs). These are scanner matches, not an assessment
that every affected code path is reachable in our test configuration.

The next build updates Go from 1.26.8 to 1.26.10 and refreshes the pinned
`debian:bookworm-slim` multi-platform digest. The upstream server/client revisions
and their dependency locks remain unchanged. Go and Debian updates cannot
remediate inherited application dependencies such as `golang.org/x/crypto`,
`golang.org/x/net`, gRPC and AMQP. Do not treat this input refresh as complete
remediation or qualify a release while its scans fail. Dependency patches or
adoption of a maintained fork need a separate reviewed source decision, updated
source/lock evidence and compatibility qualification.

Local validation of the refreshed inputs passed amd64 compilation and arm64
cross-compilation. The amd64 image passed the existing version, readiness,
object round-trip and restricted-user checks; native arm64 runtime qualification
remains a CI requirement. Grype 0.121.1 with database built
`2026-11-03T06:20:47Z` reported 269 total package findings on each architecture,
including **48 fixable High/Critical findings** (11 Critical, 37 High), all in
inherited Go dependencies. No Go standard-library or Debian
package matches remained in that fixable High/Critical set. The scan exited
nonzero as required; the candidate is **not qualified**. These timestamped
counts do not replace the mandatory fresh scan of a release's exact digest.

Grype 0.121.1 is checksum-pinned for both native runner architectures. Candidate
validation and published-image qualification now enforce the same fresh-database,
fixable High/Critical gate as maintenance. Failed scans retain reports; there are
no scanner suppressions or exceptions. `monitoring.json` continues tracking the
consumed `v0.1.0` digest until a new qualified release passes consumer adoption.
