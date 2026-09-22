import unittest

from eval_worlds_toy import (
    FileSurface,
    RecordSurface,
    compile_evaluation,
    grade_submission,
)
from eval_worlds_toy.example import (
    later_quality_task,
    make_world,
    operations_task,
    quality_task,
)


class ReferenceImplementationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = make_world()

    def test_same_world_different_seats_change_visible_evidence(self) -> None:
        quality = compile_evaluation(self.world, quality_task())
        operations = compile_evaluation(self.world, operations_task())

        self.assertEqual(quality.candidate.world_revision, operations.candidate.world_revision)
        self.assertIn("quality/supplier_review.txt", quality.candidate.files)
        self.assertNotIn("quality/supplier_review.txt", operations.candidate.files)
        self.assertNotEqual(
            quality.candidate.projection_hash, operations.candidate.projection_hash
        )

    def test_same_seat_different_dates_change_visible_evidence(self) -> None:
        earlier = compile_evaluation(self.world, quality_task())
        later = compile_evaluation(self.world, later_quality_task())

        self.assertNotIn("quality/approval_record.txt", earlier.candidate.files)
        self.assertIn("quality/approval_record.txt", later.candidate.files)
        self.assertNotEqual(earlier.candidate.projection_hash, later.candidate.projection_hash)

    def test_verifier_evidence_is_sealed(self) -> None:
        result = compile_evaluation(self.world, quality_task())

        self.assertNotIn("verifier/policy.txt", result.candidate.files)
        self.assertIn("verifier/policy.txt", result.verifier.reference_files)

    def test_explicit_grading_routes(self) -> None:
        result = compile_evaluation(self.world, quality_task())
        verdicts = grade_submission(
            result.verifier,
            "CR-17 is pending and is not approved.",
        )
        self.assertEqual(verdicts, {"Q1": True, "Q2": True})

    def test_surface_adapters_share_one_projection(self) -> None:
        result = compile_evaluation(self.world, quality_task())
        files = FileSurface(result.candidate)
        records = RecordSurface(result.candidate)

        self.assertEqual(files.list_files(), list(records.paths()))
        self.assertEqual(
            records.search("SL-4"),
            [("quality/supplier_review.txt", "Supplier SL-4 remains conditionally qualified.")],
        )


if __name__ == "__main__":
    unittest.main()
