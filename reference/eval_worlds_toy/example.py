"""A fully fictional world used by the reference tests and toy experiments."""

from datetime import date

from .core import Artifact, CanonicalWorld, Check, Seat, Task


def make_world() -> CanonicalWorld:
    return CanonicalWorld(
        revision="northstar-r1",
        seats={
            "quality_lead": Seat("quality_lead", frozenset({"all", "quality"})),
            "operations_lead": Seat(
                "operations_lead", frozenset({"all", "operations"})
            ),
        },
        artifacts=(
            Artifact(
                path="company/calendar.txt",
                content="Quarterly review occurs on 2026-01-15.",
                visible_from=date(2026, 1, 1),
                readable_by=frozenset({"all"}),
            ),
            Artifact(
                path="quality/supplier_review.txt",
                content="Supplier SL-4 remains conditionally qualified.",
                visible_from=date(2026, 1, 5),
                readable_by=frozenset({"quality"}),
            ),
            Artifact(
                path="operations/change_request.txt",
                content="CR-17 requests a supplier change; status is pending.",
                visible_from=date(2026, 1, 6),
                readable_by=frozenset({"quality", "operations"}),
            ),
            Artifact(
                path="quality/approval_record.txt",
                content="CR-17 was approved on 2026-02-01.",
                visible_from=date(2026, 2, 1),
                readable_by=frozenset({"quality"}),
            ),
            Artifact(
                path="verifier/policy.txt",
                content="A pending change must not be described as approved.",
                visible_from=date(2026, 1, 1),
                readable_by=frozenset({"quality"}),
                verifier_only=True,
            ),
        ),
    )


def quality_task() -> Task:
    return Task(
        task_id="quality-review",
        world_revision="northstar-r1",
        world_date=date(2026, 1, 10),
        seat_id="quality_lead",
        request="Write a short status note for change request CR-17.",
        deliverable_path="deliverables/status_note.txt",
        verifier_paths=("verifier/policy.txt",),
        checks=(
            Check("Q1", "deterministic", "CR-17"),
            Check("Q2", "semantic", "pending|not approved"),
        ),
    )


def operations_task() -> Task:
    return Task(
        task_id="operations-review",
        world_revision="northstar-r1",
        world_date=date(2026, 1, 10),
        seat_id="operations_lead",
        request="Summarize the operational status of change request CR-17.",
        deliverable_path="deliverables/operations_note.txt",
        verifier_paths=("verifier/policy.txt",),
        checks=(Check("O1", "deterministic", "CR-17"),),
    )


def later_quality_task() -> Task:
    return Task(
        task_id="quality-review-after-approval",
        world_revision="northstar-r1",
        world_date=date(2026, 2, 2),
        seat_id="quality_lead",
        request="Write the current status of change request CR-17.",
        deliverable_path="deliverables/current_status.txt",
        verifier_paths=("verifier/policy.txt",),
        checks=(Check("L1", "deterministic", "approved"),),
    )
