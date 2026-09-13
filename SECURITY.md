# Security policy

Railproof is security-sensitive alpha software. Do not rely on it as the only control for production systems without reviewing the policy, integration boundary, and evidence behavior.

## Supported versions

Only the latest commit on `main` is currently supported.

## Reporting a vulnerability

During the private preview, report vulnerabilities directly to the repository owner through GitHub. After public release, use GitHub private vulnerability reporting. Include the affected commit, policy, normalized event, expected decision, actual decision, and whether the underlying executor was reached. Do not open a public issue for an unpatched vulnerability.

## Security boundary

Railproof controls only calls made through `GuardedTools` or an integration that passes every action through the same decision contract. Direct access to an underlying executor bypasses Railproof. Keep executors private, default policies to deny, protect approval signing keys, and treat labels and provenance as application-attested inputs.
