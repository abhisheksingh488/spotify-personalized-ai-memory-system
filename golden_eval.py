import subprocess
import sys


TEST_GROUPS = [
    {
        "case_id": "cross_subject_isolation_001",
        "tests": [
            "tests/test_security.py::test_cross_subject_memory_is_not_returned",
            "tests/test_security.py::test_cross_subject_memory_deletion_is_blocked",
        ],
    },
    {
        "case_id": "policy_block_001",
        "tests": [
            "tests/test_security.py::test_policy_flagged_memory_candidate_is_not_accepted",
        ],
    },
    {
        "case_id": "deletion_propagation_001",
        "tests": [
            "tests/test_deletion.py::test_memory_deletion_contract",
        ],
    },
    {
        "case_id": "correction_supersedes_001",
        "tests": [
            "tests/test_correction.py::test_memory_correction_supersedes_old_memory",
        ],
    },
    {
        "case_id": "provenance_required_001",
        "tests": [
            "tests/test_api_contracts.py::test_context_compose_contract",
        ],
    },
    {
        "case_id": "explicit_preference_recall_001",
        "tests": [
            "tests/test_preference_recall.py::test_explicit_preference_recall",
        ],
    },
    {
        "case_id": "age_protection_001",
        "tests": [
            "tests/test_policy_governance.py::test_minor_is_blocked",
            "tests/test_policy_governance.py::test_child_is_blocked",
            "tests/test_policy_governance.py::test_invalid_age_group_is_rejected",
        ],
    },
    {
        "case_id": "geography_policy_001",
        "tests": [
            "tests/test_policy_governance.py::test_adult_normal_geography_allowed",
            "tests/test_policy_governance.py::test_blocked_geography_is_rejected",
        ],
    },
    {
        "case_id": "consent_governance_001",
        "tests": [
            "tests/test_policy_governance.py::test_consent_false_is_not_governance_approval",
            "tests/test_policy_governance.py::test_unknown_age_is_allowed_without_inference",
        ],
    },
]


def run_case(case):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *case["tests"],
        ],
        capture_output=True,
        text=True,
    )

    return result.returncode == 0, result.stdout + result.stderr


def main():
    print("=" * 60)
    print("Spotify Memory Golden Evaluation")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for case in TEST_GROUPS:
        success, output = run_case(case)

        if success:
            passed += 1
            print(f"[PASS] {case['case_id']}")
        else:
            failed += 1
            print(f"[FAIL] {case['case_id']}")
            print(output)

    total = len(TEST_GROUPS)
    score = (passed / total * 100) if total else 0

    print()
    print("-" * 60)
    print(f"Total : {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Score : {score:.2f}%")
    print("-" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())