#!/usr/bin/env python3
"""Run pre-commit hooks on all files in the repository.

File used to test running the hooks in the CI/CD pipeline independently of the shell.
"""
from __future__ import annotations

import subprocess  # nosec
import sys

HOOK_ALIAS_TO_OUTPUT_MAPPING: dict[str, tuple[bool, list[str], list[str]]] = {
    "default": (
        True,
        ["Valid Entities"],
        [
            "Failed to validate one or more entities.",
            "There were no valid entities among the supplied sources.",
        ],
    ),
    "invalid-entities": (
        False,
        [
            "Failed to validate one or more entities.",
            "There were no valid entities among the supplied sources.",
        ],
        ["Valid Entities"],
    ),
    "mixed-validity": (
        False,
        ["Failed to validate one or more entities.", "Valid Entities"],
        ["There were no valid entities among the supplied sources."],
    ),
    "quiet": (
        True,
        [],
        [
            "Failed to validate one or more entities.",
            "Valid Entities",
            "There were no valid entities among the supplied sources.",
        ],
    ),
    "quiet-mixed-validity": (
        False,
        ["Failed to validate one or more entities."],
        ["Valid Entities", "There were no valid entities among the supplied sources."],
    ),
    "fail-fast": (
        False,
        ["contains an invalid SOFT"],
        [
            "Failed to validate one or more entities.",
            "Valid Entities",
            "There were no valid entities among the supplied sources.",
        ],
    ),
}
"""Mapping of hook aliases to their expected output.

Note, the first element in the tuple is a boolean indicating whether the hook should
pass or fail. Then follows a list of strings that should be present in the output
of the hook. Finally, there is a list of strings that should not be present in the
output of the hook.
"""


def main(hook: str, options: list[str]) -> None:
    """Run pre-commit hooks on all files in the repository."""
    run_pre_commit = (
        "pre-commit run -c .github/utils/.pre-commit-config_testing.yaml "
        "--all-files --verbose"
    )

    result = subprocess.run(
        f"{run_pre_commit} {' '.join(_ for _ in options)} {hook}",
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,  # nosec
    )

    decoded_stdout = result.stdout.decode()

    expected_success: bool = HOOK_ALIAS_TO_OUTPUT_MAPPING[hook][0]
    expected_outputs: list[str] = HOOK_ALIAS_TO_OUTPUT_MAPPING[hook][1]
    unexpected_outputs: list[str] = HOOK_ALIAS_TO_OUTPUT_MAPPING[hook][2]

    if expected_success and result.returncode != 0:
        print(
            f"Expected success, but the hook ({hook}) failed.\n\n",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(decoded_stdout)
    elif not expected_success and result.returncode == 0:
        print(
            f"Expected failure, but the hook ({hook}) passed.\n\n",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(decoded_stdout)

    for expected_output in expected_outputs:
        if expected_output not in decoded_stdout:
            print(
                f"Expected output {expected_output!r} could not be found when running "
                f"the hook: {hook}.\n\n",
                file=sys.stderr,
                flush=True,
            )
            sys.exit(decoded_stdout)

    for unexpected_output in unexpected_outputs:
        if unexpected_output in decoded_stdout:
            print(
                f"Unexpected output {unexpected_output!r} was found when running the "
                f"hook: {hook}.\n\n",
                file=sys.stderr,
                flush=True,
            )
            sys.exit(decoded_stdout)

    print(f"Successfully ran {hook} hook.\n\n", flush=True)
    print(decoded_stdout, flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise sys.exit("Missing arguments")

    # "Parse" arguments
    # The first argument should be the hook id
    if sys.argv[1] not in HOOK_ALIAS_TO_OUTPUT_MAPPING:
        raise sys.exit(
            f"Invalid hook id: {sys.argv[1]}\n"
            "The hook id should be the first argument. Any number of hook options "
            "can then follow."
        )

    try:
        main(
            hook=sys.argv[1],
            options=sys.argv[2:] if len(sys.argv) > 2 else [],
        )
    except Exception as exc:
        sys.exit(str(exc))
