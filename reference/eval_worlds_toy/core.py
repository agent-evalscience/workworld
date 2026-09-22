"""A compact implementation of persistent-world evaluation materialization.

This module is deliberately small. It demonstrates the architectural boundary
without importing production code or reproducing a real evaluation world.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping


def stable_hash(value: object) -> str:
    """Return a stable content hash for JSON-compatible dataclasses and values."""

    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Seat:
    seat_id: str
    roles: frozenset[str]


@dataclass(frozen=True)
class Artifact:
    path: str
    content: str
    visible_from: date
    readable_by: frozenset[str]
    verifier_only: bool = False


@dataclass(frozen=True)
class Check:
    check_id: str
    route: str
    expected: str

    def __post_init__(self) -> None:
        if self.route not in {"deterministic", "semantic"}:
            raise ValueError(f"unsupported check route: {self.route}")


@dataclass(frozen=True)
class Task:
    task_id: str
    world_revision: str
    world_date: date
    seat_id: str
    request: str
    deliverable_path: str
    verifier_paths: tuple[str, ...]
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class CanonicalWorld:
    revision: str
    seats: Mapping[str, Seat]
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True)
class CandidateEnvironment:
    world_revision: str
    world_date: date
    seat_id: str
    request: str
    deliverable_path: str
    files: Mapping[str, str]
    projection_hash: str


@dataclass(frozen=True)
class VerifierPackage:
    world_revision: str
    task_id: str
    reference_files: Mapping[str, str]
    checks: tuple[Check, ...]
    package_hash: str


@dataclass(frozen=True)
class BuildResult:
    candidate: CandidateEnvironment
    verifier: VerifierPackage


def _visible_to(artifact: Artifact, seat: Seat, on_date: date) -> bool:
    return artifact.visible_from <= on_date and bool(artifact.readable_by & seat.roles)


def compile_evaluation(world: CanonicalWorld, task: Task) -> BuildResult:
    """Materialize candidate and verifier views from one frozen world revision."""

    if task.world_revision != world.revision:
        raise ValueError("task and world revisions differ")
    if task.seat_id not in world.seats:
        raise KeyError(f"unknown seat: {task.seat_id}")

    seat = world.seats[task.seat_id]
    artifact_index = {artifact.path: artifact for artifact in world.artifacts}
    if len(artifact_index) != len(world.artifacts):
        raise ValueError("artifact paths must be unique")

    candidate_files = {
        artifact.path: artifact.content
        for artifact in world.artifacts
        if _visible_to(artifact, seat, task.world_date) and not artifact.verifier_only
    }

    missing_references = set(task.verifier_paths) - set(artifact_index)
    if missing_references:
        raise KeyError(f"unknown verifier paths: {sorted(missing_references)}")
    reference_files = {
        path: artifact_index[path].content for path in task.verifier_paths
    }

    projection_payload = {
        "world_revision": world.revision,
        "world_date": task.world_date,
        "seat_id": seat.seat_id,
        "files": candidate_files,
    }
    verifier_payload = {
        "world_revision": world.revision,
        "task_id": task.task_id,
        "reference_files": reference_files,
        "checks": task.checks,
    }

    candidate = CandidateEnvironment(
        world_revision=world.revision,
        world_date=task.world_date,
        seat_id=seat.seat_id,
        request=task.request,
        deliverable_path=task.deliverable_path,
        files=candidate_files,
        projection_hash=stable_hash(projection_payload),
    )
    verifier = VerifierPackage(
        world_revision=world.revision,
        task_id=task.task_id,
        reference_files=reference_files,
        checks=task.checks,
        package_hash=stable_hash(verifier_payload),
    )
    return BuildResult(candidate=candidate, verifier=verifier)


SemanticJudge = Callable[[str, Check, Mapping[str, str]], bool]


class KeywordSemanticJudge:
    """Deterministic stand-in for a source-grounded semantic grading session."""

    def __call__(
        self, submission: str, check: Check, reference_files: Mapping[str, str]
    ) -> bool:
        expected_terms = [term.strip().lower() for term in check.expected.split("|")]
        lowered = submission.lower()
        return all(term in lowered for term in expected_terms) and bool(reference_files)


def grade_submission(
    verifier: VerifierPackage,
    submission: str,
    semantic_judge: SemanticJudge | None = None,
) -> dict[str, bool]:
    """Apply explicit deterministic and semantic routes to one submission."""

    judge = semantic_judge or KeywordSemanticJudge()
    verdicts: dict[str, bool] = {}
    for check in verifier.checks:
        if check.route == "deterministic":
            verdicts[check.check_id] = check.expected.lower() in submission.lower()
        else:
            verdicts[check.check_id] = judge(
                submission, check, verifier.reference_files
            )
    return verdicts


class FileSurface:
    """Read-only filesystem-like adapter over an already compiled projection."""

    def __init__(self, environment: CandidateEnvironment):
        self.environment = environment

    def list_files(self) -> list[str]:
        return sorted(self.environment.files)

    def read(self, path: str) -> str:
        return self.environment.files[path]


class RecordSurface:
    """Read-only record-search adapter over the same compiled projection."""

    def __init__(self, environment: CandidateEnvironment):
        self.environment = environment

    def search(self, query: str) -> list[tuple[str, str]]:
        term = query.lower()
        return sorted(
            (path, content)
            for path, content in self.environment.files.items()
            if term in path.lower() or term in content.lower()
        )

    def paths(self) -> Iterable[str]:
        return sorted(self.environment.files)
