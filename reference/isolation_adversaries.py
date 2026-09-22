"""Seed contract violations into the public-safe reference world and verify detection.

This is deterministic infrastructure testing. It does not call a model and does not
stand in for production-world validation.
"""

from dataclasses import replace

from eval_worlds_toy import FileSurface, compile_evaluation, stable_hash
from eval_worlds_toy.example import make_world, operations_task, quality_task


def _projection_hash(candidate):
    return stable_hash(
        {
            "world_revision": candidate.world_revision,
            "world_date": candidate.world_date,
            "seat_id": candidate.seat_id,
            "files": candidate.files,
        }
    )


def detect(world, task, candidate, verifier, record_paths=None):
    if candidate.world_revision != world.revision or verifier.world_revision != world.revision:
        return "revision_gate"

    seat = world.seats[task.seat_id]
    index = {artifact.path: artifact for artifact in world.artifacts}
    for path in candidate.files:
        artifact = index.get(path)
        if artifact is None:
            return "manifest_gate"
        if artifact.verifier_only:
            return "package_isolation"
        if artifact.visible_from > task.world_date:
            return "date_projection"
        if not (artifact.readable_by & seat.roles):
            return "seat_projection"

    if candidate.projection_hash != _projection_hash(candidate):
        return "manifest_gate"

    if record_paths is not None and set(FileSurface(candidate).list_files()) != set(record_paths):
        return "surface_conformance"

    return None


def main():
    world = make_world()
    quality = quality_task()
    quality_build = compile_evaluation(world, quality)
    operations = operations_task()
    operations_build = compile_evaluation(world, operations)
    contents = {artifact.path: artifact.content for artifact in world.artifacts}

    cases = [
        (
            "verifier_file_on_candidate",
            quality,
            replace(
                quality_build.candidate,
                files={
                    **quality_build.candidate.files,
                    "verifier/policy.txt": contents["verifier/policy.txt"],
                },
            ),
            quality_build.verifier,
            None,
            "package_isolation",
        ),
        (
            "future_file_on_early_date",
            quality,
            replace(
                quality_build.candidate,
                files={
                    **quality_build.candidate.files,
                    "quality/approval_record.txt": contents["quality/approval_record.txt"],
                },
            ),
            quality_build.verifier,
            None,
            "date_projection",
        ),
        (
            "role_inaccessible_file",
            operations,
            replace(
                operations_build.candidate,
                files={
                    **operations_build.candidate.files,
                    "quality/supplier_review.txt": contents["quality/supplier_review.txt"],
                },
            ),
            operations_build.verifier,
            None,
            "seat_projection",
        ),
        (
            "revision_mismatch",
            quality,
            replace(quality_build.candidate, world_revision="northstar-r0"),
            quality_build.verifier,
            None,
            "revision_gate",
        ),
        (
            "projection_hash_tamper",
            quality,
            replace(quality_build.candidate, projection_hash="tampered"),
            quality_build.verifier,
            None,
            "manifest_gate",
        ),
        (
            "record_surface_divergence",
            quality,
            quality_build.candidate,
            quality_build.verifier,
            ["operations/change_request.txt"],
            "surface_conformance",
        ),
    ]

    detected = 0
    print("adversary\texpected_stage\tdetected_stage\tpass")
    for name, task, candidate, verifier, record_paths, expected in cases:
        observed = detect(world, task, candidate, verifier, record_paths)
        ok = observed == expected
        detected += int(ok)
        print(f"{name}\t{expected}\t{observed}\t{int(ok)}")

    print(f"total\t{len(cases)}\t{detected}\t{detected / len(cases):.3f}")
    if detected != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
