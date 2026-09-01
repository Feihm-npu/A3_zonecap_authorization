# C4 Pinned-SINT Baseline Protocol

Status: S2 exp-20 protocol, fixed before execution.

## Baseline identity and execution boundary

The baseline is SINT Protocol commit
`2461a911b8c3d7ed9da3f7662b33678f688eb826`, previously built and checked in
S1. Exp-20 checks the commit and hashes the exact whitepaper, revocation store,
gateway, approval queue, and in-memory/Redis revocation-bus sources before using
the compiled JavaScript modules. Dependencies come from the pinned lockfile with
pnpm 9.15.0; no current-main behavior or published latency is substituted.

The executable comparison covers only SINT's `PolicyGateway`,
`RevocationStore`, and `ApprovalQueue`. It does not treat documentation or a
functional reimplementation as an executed baseline.

## Fixed traces

1. **Local revocation:** a valid T0 request is intercepted before revocation,
   once after revocation issuance but before the resolver-local store is
   updated, and once after delivery to that store. The strict issuance-time
   metric from exp-19 and SINT's delivered-store decision are both retained.
2. **Revoke during quorum:** two distinct T2 requests for the same resource are
   independently escalated and enqueued with a two-of-three quorum. After one
   vote on each, token A is revoked locally; the second votes are then applied.
   The queue resolution is recorded separately from a fresh gateway
   interception of request A.
3. **Independent conflicts:** both same-resource requests receive quorum. The
   number of approved queue resolutions and the presence or absence of a
   cross-request winner are reported; approval is not mislabeled as physical
   execution.
4. **Missing approval:** a third request receives only one of two required
   votes and reaches the queue's real timer fallback. This checks baseline
   terminal progress, not latency.

## Comparison rules

Feature support is `full` only when the pinned executable directly produces the
registered state transition. `partial` means the primitive exists but an
integration contract is required. `absent` means the same-resource trace has no
winner/arbitration transition in the tested implementation. `N/A` is used when
the ZoneCap property has no corresponding SINT state object; it is never scored
as a failure.

The structural run passes if the pinned sources match, pre-delivery and
post-delivery decisions are obtained, delivered revocation denies, quorum vote
deduplication works, the missing-approval request times out, and a fresh gateway
check denies the revoked token. Whether the stale pre-delivery request is
allowed, whether the already-enqueued revoked request resolves approved, and
whether both conflicting requests resolve approved are reported as baseline
state-machine deltas rather than hard-coded as C4 pass criteria.

