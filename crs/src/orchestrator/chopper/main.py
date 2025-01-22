#!/usr/bin/env python3
"""
Chopper is a tool that uses git bisect to find the first bad commit.
"""

import json
import os
import subprocess
import sys
import traceback
from typing import Optional, Set, Tuple
from pathlib import Path
from tqdm import tqdm

MAX_BINARY_STEPS = 20  # Maximum binary search attempts before falling back to linear


class CommitTester:
    def __init__(
        self,
        cp_src: str,
        cp_path: str,
        build_script: str,
        test_script: str,
        output_dir: str,
    ):
        self.cp_src = cp_src
        self.cp_path = cp_path
        self.build_script = build_script
        self.test_script = test_script
        self.output_dir = output_dir
        self.tested_commits = {}

    def run_cmd(self, cmd: str, cwd: str) -> subprocess.CompletedProcess:
        """Run a command in specified directory and return the result"""
        return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)

    def get_commit_list(self) -> list[str]:
        """Get list of all commits from newest to oldest"""
        result = self.run_cmd("git log --format=%H", self.cp_src)
        return result.stdout.strip().split("\n")

    def checkout_commit(self, commit: str) -> bool:
        """Checkout specific commit"""
        result = self.run_cmd(f"git checkout {commit}", self.cp_src)
        return result.returncode == 0

    def test_commit(self, commit: str) -> Tuple[bool, bool]:
        """
        Test a specific commit
        Returns: (can_build, is_good)
        - can_build: Whether commit builds successfully
        - is_good: Whether tests pass (commit is "good")
        """
        # Check if we've already tested this commit
        if commit in self.tested_commits:
            return self.tested_commits[commit]

        if not self.checkout_commit(commit):
            self.tested_commits[commit] = (False, False)
            return False, False

        # Try to build
        build_result = self.run_cmd(self.build_script, self.cp_path)
        # print(build_result)
        if build_result.returncode != 0:
            print(f"Build failed for commit {commit[:8]}")
            self.tested_commits[commit] = (False, False)
            return False, False

        # Run test
        test_result = self.run_cmd(self.test_script, self.cp_path)

        # Check output directory for test results
        output_files = list(Path(self.output_dir).glob("**/*stderr.log"))
        if not output_files:
            self.tested_commits[commit] = (True, False)
            return True, False

        latest_output = max(output_files, key=lambda p: p.stat().st_mtime)
        test_output = latest_output.read_text()

        # Commit is "good" if test passes
        is_good = test_result.returncode == 0 and "FAILED" not in test_output
        self.tested_commits[commit] = (True, is_good)
        return True, is_good

    def binary_search_good_commit(
        self, commits: list[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Find the transition point between good and bad commits
        Returns: (bad_commit, good_commit, bug_inducing_commit)
        - bad_commit: Known bad commit (HEAD)
        - good_commit: Last known good commit
        - bug_inducing_commit: First bad commit after good_commit (good_commit + 1)
        """

        print(f"In commit list: {commits[0]}, last element: {commits[-1]}")
        steps = 0
        left, right = len(commits) - 1, 0
        last_good_commit = None
        head_commit = commits[0]  # Store HEAD commit

        self.tested_commits = {}  # Dictionary mapping commit -> (can_build, is_good)

        print("\nBinary Search Debug:")
        print("==================")

        while steps < MAX_BINARY_STEPS and left >= right:
            mid = (left + right) // 2
            commit = commits[mid]

            if commit in self.tested_commits:
                can_build, is_good = self.tested_commits[commit]
            else:
                print(f"\nStep {steps + 1}")
                print(f"Checking commit {commit[:8]} (#{len(commits) - mid})")
                print(f"Search range: commits[{right}:{left}]")
                can_build, is_good = self.test_commit(commit)
                print(f"Can build: {can_build}, Is good: {is_good}")

            if not can_build:
                print("Build failed -> Moving left")
                left = mid - 1
            elif is_good:
                last_good_commit = commit
                # Check if next commit exists and is bad - we found the transition
                if mid + 1 < len(commits):
                    next_commit = commits[mid + 1]
                    if next_commit in self.tested_commits:
                        next_can_build, next_is_good = self.tested_commits[next_commit]
                    else:
                        next_can_build, next_is_good = self.test_commit(next_commit)

                    if next_can_build and not next_is_good:
                        print(f"\nFound transition point!")
                        print(f"Last good commit: {commit[:8]}")
                        print(f"First bad commit: {next_commit[:8]}")
                        return head_commit, commit, next_commit

                print("Test passed -> Moving left")
                left = mid - 1
            else:
                print("Test failed -> Moving right")
                right = mid + 1

            steps += 1

        # If we found a good commit but no clear transition
        if last_good_commit and last_good_commit != commits[-1]:
            idx = commits.index(last_good_commit)
            if idx + 1 < len(commits):
                return head_commit, last_good_commit, commits[idx - 1]

        print("\nSearch completed without finding clear transition")
        return None, None, None

    def linear_search_good_commit(self, commits: list[str]) -> Optional[str]:
        """
        Find good commit using linear search, skipping already tested commits
        """
        progress_bar = tqdm(commits, desc="Linear search", unit="commit")
        for commit in progress_bar:
            if commit in self.tested_commits:
                continue

            progress_bar.write(f"\nTrying commit {commit[:8]}")
            can_build, is_good = self.test_commit(commit)

            if can_build and is_good:
                return commit
        return None


def find_bug_commit(bug_info_path: str, output_path: str):
    """Main entry point"""
    with open(bug_info_path) as f:
        bug_info = json.load(f)
    print(bug_info["cp_sources"][0], output_path)
    cp_path = bug_info["cp_path"]
    cp_src = os.path.join(cp_path, "src", bug_info["cp_sources"][0]["name"])
    output_dir = os.path.join(cp_path, "out", "output")

    build_script = bug_info["build_script"]
    test_script = (
        f"{bug_info['test_script']} "
        f"{os.path.join(cp_path, 'tests', bug_info['failing_test_identifiers'][0])}"
    )

    tester = CommitTester(cp_src, cp_path, build_script, test_script, output_dir)
    print("Verifying current commit fails...")
    can_build, is_good = tester.test_commit("HEAD")
    if can_build and is_good:
        print("ERROR: Current commit should fail but doesn't")
        return

    # Get list of all commits
    all_commits = tester.get_commit_list()
    print(f"Found {len(all_commits)} total commits")

    # Try binary search
    print("\nStarting binary search phase...")
    bad_commit, good_commit, bug_commit = tester.binary_search_good_commit(all_commits)

    if good_commit and bug_commit:
        print(f"\nSearch Results:")
        print(f"Known bad commit (HEAD): {bad_commit[:8]}")

        # Find index of good commit to get surrounding commits
        idx = all_commits.index(good_commit)

        good_minus_one = all_commits[idx - 1] if idx > 0 else None
        good_plus_one = all_commits[idx + 1] if idx + 1 < len(all_commits) else None

        print(f"Context around transition:")
        if good_minus_one:
            print(f"Commit AFTER good: {good_minus_one[:8]} (bug inducing commit)")
        print(f"Last good commit: {good_commit[:8]}")
        if good_plus_one:
            print(f"Commit BEFORE good: {good_plus_one[:8]}")

        with open(output_path, "w") as f:
            f.write(f"{bug_commit}\n{bug_info['cp_sources'][0]['name']}")
    else:
        print("Failed to find transition point between good and bad commits")


if __name__ == "__main__":
    """
    Entry of the Chopper tool.
    """

    bug_info_json_path = sys.argv[1]
    output_path = sys.argv[2]
    print(bug_info_json_path)
    try:
        find_bug_commit(sys.argv[1], sys.argv[2])
        # with open(bug_info_json_path, "r") as bug_info_json_file:
        #   bug_info = json.load(bug_info_json_file)
        #    main(bug_info, output_path)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        print(f"Error: {e}")
        sys.exit(1)
