"""Safe isolation reporting for CLI configuration output."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from forgeweave.contracts import ExecutionProfile, IsolationClaim


@dataclass(frozen=True)
class IsolationClaimView:
    """One independently reported containment dimension."""

    level: str
    backend: str
    measured: bool
    evidence: str | None = None


@dataclass(frozen=True)
class IsolationView:
    """CLI-safe isolation summary that avoids overstating sandbox guarantees."""

    profile_id: str
    restricted_execution_measured: bool
    claims: dict[str, IsolationClaimView]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable mapping."""

        return {
            "profile_id": self.profile_id,
            "restricted_execution_measured": self.restricted_execution_measured,
            "claims": {name: asdict(claim) for name, claim in self.claims.items()},
        }


def default_host_isolation_profile() -> ExecutionProfile:
    """Return ForgeWeave's honest default local execution profile."""

    return ExecutionProfile(
        profile_id="local-host-user.v1",
        filesystem=IsolationClaim(level="host-user", backend="host-filesystem", measured=False),
        network=IsolationClaim(level="shared-egress", backend="host-network", measured=False),
        credentials=IsolationClaim(level="host-user", backend="process-environment", measured=False),
        process_tree=IsolationClaim(level="host-process", backend="subprocess", measured=False),
        resources=IsolationClaim(level="best-effort", backend="process", measured=False),
    )


def isolation_view(profile: ExecutionProfile) -> IsolationView:
    """Project an `ExecutionProfile` into stable CLI JSON."""

    return IsolationView(
        profile_id=profile.profile_id,
        restricted_execution_measured=profile.has_measured_restricted_execution,
        claims={
            "filesystem": _claim_view(profile.filesystem),
            "network": _claim_view(profile.network),
            "credentials": _claim_view(profile.credentials),
            "process_tree": _claim_view(profile.process_tree),
            "resources": _claim_view(profile.resources),
        },
    )


def _claim_view(claim: IsolationClaim) -> IsolationClaimView:
    return IsolationClaimView(level=claim.level, backend=claim.backend, measured=claim.measured, evidence=claim.evidence)
