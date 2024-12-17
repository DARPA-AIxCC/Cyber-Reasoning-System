#!/usr/bin/env python3

import os
import sys
from enum import Enum
from os.path import join as pjoin
from pathlib import Path

from util import run_cmd_in_dir
import re


class Action(Enum):
    BUILD = 1
    TEST = 2


def decide_pass_fail(
    output_dir: str,
    crash_location: re.Pattern[str],
    sanitizer_pattern: re.Pattern[str],
    action: Action,
) -> bool:
    """
    NOTE: Main library entry point.

    Decides whether execution of the test script / build script ok/fail.
    By right this should be told us by the test script. However, do to the
    complication in exposing exit code from ./run.sh, we check file output
    here.

    If in the future the run script can consistently relay the exit code,
    do something else.

    Returns:
        - True if the test/build script passes
        - False if the test/build script fails
    """
    run_res_names = os.listdir(output_dir)
    run_res_names = [
        name for name in run_res_names if os.path.isdir(pjoin(output_dir, name))
    ]
    build_dir_names = [name for name in run_res_names if "--build" in name]
    test_dir_names = [name for name in run_res_names if "--run_pov" in name]

    if action == Action.BUILD:
        # find the latest build result dir
        assert len(build_dir_names) > 0
        latest_build_name = sorted(build_dir_names)[-1]
        latest_build_dir = pjoin(output_dir, latest_build_name)
        # NOTE: for build, check the exitcode since it has been quite stable
        exitcode_file = pjoin(latest_build_dir, "exitcode")
        exitcode = int(Path(exitcode_file).read_text())
        build_ok = exitcode == 0
        print(f"\t[decide_pass_fail] build ok? {build_ok}")
        return build_ok

    elif action == Action.TEST:
        assert len(test_dir_names) > 0
        latest_test_name = sorted(test_dir_names)[-1]
        latest_test_dir = pjoin(output_dir, latest_test_name)
        # for test, let's read the stdout + stderr to decide
        stderr_file = pjoin(latest_test_dir, "stderr.log")
        stderr_content = Path(stderr_file).read_text()
        stdout_file = pjoin(latest_test_dir, "stdout.log")
        stdout_content = Path(stdout_file).read_text()
        project_output = stdout_content + stderr_content

        test_fail = re.search(sanitizer_pattern, project_output) is not None
        test_ok = not test_fail
        print(f"\t[decide_pass_fail] test ok? {test_ok}")
        return test_ok

    else:
        raise ValueError(f"Unknown action: {action}")


def bisect_entry(
    build_script: str,
    test_script: str,
    cp_path: str,
    test_output_dir: str,
    crash_location: re.Pattern[str],
    pattern: re.Pattern[str],
):
    """
    Main entry if running this script standalone.

    Returns:
        - An int code according to specification of `git bisect`.
            - 0 if the current commit is good
            - 1 if the current commit is bad
            - 125 if the current commit should be skipped
    """
    run_cmd_in_dir(build_script, cp_path)
    build_ok = decide_pass_fail(test_output_dir, crash_location, pattern, Action.BUILD)
    if not build_ok:
        # should skip this commit
        return 125

    run_cmd_in_dir(test_script, cp_path)
    test_ok = decide_pass_fail(test_output_dir, crash_location, pattern, Action.TEST)
    if test_ok:
        return 0
    else:
        return 1


if __name__ == "__main__":
    # This script can be run directly, as the script to be provided to `git bisect`.
    # ASSUMPTION:
    #    1. we are already in the target git repository.
    #    2. someone else will handle the git checkout logic

    build_script = sys.argv[1]  # provided by the setup
    test_script = sys.argv[2]  # provided by the setup
    cp_path = sys.argv[3]  # provided by the setup
    test_output_dir = sys.argv[4]
    pattern = re.compile(sys.argv[5])

    exit_code = bisect_entry(
        build_script, test_script, cp_path, test_output_dir, pattern
    )
    exit(exit_code)
