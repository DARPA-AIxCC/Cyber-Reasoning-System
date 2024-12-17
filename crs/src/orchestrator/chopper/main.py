"""
Chopper is a tool that uses git bisect to find the first bad commit.
"""

import json
import os
import subprocess
import sys
import traceback
import re
from os.path import join as pjoin
from typing import Tuple
from git import Repo
from oracle import Action, decide_pass_fail, bisect_entry
from util import cd, run_cmd_in_dir


def get_curr_commit_hash(cp_src: str) -> str:
    """
    Get the current commit hash.
    """
    with cd(cp_src):
        cp = subprocess.run("git rev-parse HEAD", shell=True, stdout=subprocess.PIPE)
    return cp.stdout.decode("utf-8").strip()


def get_first_commit_hash(cp_src: str) -> str:
    """
    Get the first commit hash.
    """
    with cd(cp_src):
        cp = subprocess.run(
            "git rev-list --max-parents=0 HEAD", shell=True, stdout=subprocess.PIPE
        )
    return cp.stdout.decode("utf-8").strip()


def repo_stash_checkout(cp_src: str, commit_hash: str):
    """
    Stash changes and checkout the commit hash.

    We just stash to make sure the checkout does not fail.
    NOTE: the stash will not be popped.
    """
    run_cmd_in_dir("git stash", cp_src)
    run_cmd_in_dir(f"git checkout {commit_hash}", cp_src)


def run_bisect_linear(
    cp_src: str,
    cp_path: str,
    bad_commit: str,
    build_script: str,
    test_script: str,
    output_dir: str,
    crash_location: str,
    pattern: str,
    solo_repo: bool = True,
) -> str | None:
    """
    Returns:
        - hash of the first bad commit if found
        - None if the bisect fails
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_for_bisect = pjoin(script_dir, "oracle.py")

    # Check if the repository loaded correctly
    repo = Repo(cp_src)
    bug_introducing_commits = []
    if not repo.bare:
        print("Repo at {} successfully loaded.".format(cp_src))
        # List all commits sorted by date (most recent first)
        commits = list(
            repo.iter_commits()
        )  # or use 'main' depending on your branch name
        commits.sort(key=lambda commit: commit.committed_datetime, reverse=True)

        # Check if last commit is also faulty, then
        last_commit = commits[-1]
        repo.git.checkout(last_commit.hexsha)
        # query oracle
        ret = bisect_entry(
            build_script, test_script, cp_path, output_dir, crash_location, pattern
        )
        if (
            ret == 1 and not solo_repo
        ):  # In the case of multiple repos, ignore this repo as probably it does not exhibit the error if the commit is failing
            return None

        has_good_commit = False
        # Print commit details
        for commit in commits:
            # check out
            repo.git.checkout(commit.hexsha)
            # query oracle
            ret = bisect_entry(
                build_script, test_script, cp_path, output_dir, crash_location, pattern
            )
            if ret == 0:
                has_good_commit = True
                # good commit
                break
            elif ret == 1:
                # bad commit
                bug_introducing_commits.append(commit.hexsha)
            else:
                # some other cases, skipped
                pass

        if solo_repo:
            if len(bug_introducing_commits) > 0:
                return bug_introducing_commits[-1]
            return None
        else:
            if has_good_commit:
                if len(bug_introducing_commits) > 0:
                    return bug_introducing_commits[-1]
                return None
            else:
                # Either this is not the faulty repo
                # or the bug is universal across the search space
                return None
    else:
        print("Could not load repository at {}.".format(cp_src))
        return None
    return 0


def run_bisect(
    cp_src: str,
    cp_path: str,
    good_commit: str,
    bad_commit: str,
    build_script: str,
    test_script: str,
    output_dir: str,
    pattern: str,
) -> str | None:
    """
    Returns:
        - hash of the first bad commit if found
        - None if the bisect fails
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_for_bisect = pjoin(script_dir, "oracle.py")

    bisect_start_cmd = f"git bisect start {bad_commit} {good_commit}"
    print(f"Starting bisect with cmd: {bisect_start_cmd}")
    run_cmd_in_dir(bisect_start_cmd, cp_src)

    bisect_cmd = f"git bisect run {script_for_bisect} {build_script} {test_script} {cp_path} {output_dir} '{pattern}'"
    print(f"Invoking git bisect with cmd: {bisect_cmd}")
    cp = run_cmd_in_dir(bisect_cmd, cp_src)

    bisect_reset_cmd = "git bisect reset"
    print(f"Resetting bisect with cmd: {bisect_reset_cmd}")
    run_cmd_in_dir(bisect_reset_cmd, cp_src)

    # process bisect output
    bisect_output = cp.stdout.decode("utf-8")
    print(f"Bisect output: {bisect_output}")

    target_info_line = ""
    for line in bisect_output.split("\n"):
        if "is the first bad commit" in line:
            target_info_line = line
            break

    if not target_info_line:
        print("Chopper failed!")
        return None
    else:
        commit = target_info_line.split(" ")[0]
        print(f"First bad commit: {commit}")
        return commit


from os.path import join


def main(bug_info, output_path) -> str | None:
    cp_path = bug_info["cp_path"]
    cp_source_names = list(
        map(
            lambda x: (join(cp_path, "src", x["name"]), str(x["name"])),
            bug_info["cp_sources"],
        )
    )

    stack_trace = bug_info["tiebreaker_files"]

    sanitizer_names = re.escape(bug_info["triggered_sanitizer"]["name"])
    sanitizer_names_compiled = re.compile(sanitizer_names)
    build_script = bug_info["build_script"]
    test_script = (
        bug_info["test_script"]
        + " "
        + pjoin(cp_path, "tests", bug_info["failing_test_identifiers"][0])
    )

    # figure out what is the output directory for ./run.sh
    output_dir = pjoin(cp_path, "out", "output")

    # verify that the current commit fails on the test
    print(f"Verifying that the current commits fails the test:")

    run_cmd_in_dir(build_script, cp_path)
    run_cmd_in_dir(test_script, cp_path)
    test_ok = decide_pass_fail(
        output_dir,
        re.compile("A"),  # re.compile(re.escape(stack_trace[0].split(":"))),
        sanitizer_names_compiled,
        Action.TEST,
    )
    if test_ok:
        print(
            "SOMETHING WRONG! Test should fail on the current version, but it is passing. Aborting."
        )
        return None

    # verify that the first commit passes on the test
    # first_commit_hash = get_first_commit_hash(cp_src)
    # print(f"Verifying that the first commit passes on the test: {first_commit_hash}")

    # repo_stash_checkout(cp_src, first_commit_hash)
    # run_cmd_in_dir(build_script, cp_path)
    # build_ok = decide_pass_fail(output_dir, sanitizer_names_compiled, Action.BUILD)
    # if not build_ok:
    #    # somehow the first commit could not be built
    #    # this is ok, since the first commit may represent incompete project state
    #    print("First commit cannot be built. Just skip it.")
    # else:  # can build on initial commit
    #     run_cmd_in_dir(test_script, cp_path)
    #     test_ok = decide_pass_fail(output_dir, sanitizer_names_compiled, Action.TEST)
    #     if not test_ok:
    #         # first commit fails ...
    #         print(
    #             "First commit fails on the test. Aborting and returning the first commit."
    #         )
    #        return first_commit_hash

    # done with sanity checking; let's do the bisect

    if len(cp_source_names) == 1:
        cp_src = cp_source_names[0][0]
        curr_commit_hash = get_curr_commit_hash(cp_src)
        print("Starting bisect for single repo case ...")
        repo_stash_checkout(cp_src, curr_commit_hash)
        chopper_result: str | None = run_bisect_linear(
            cp_src,
            cp_path,
            curr_commit_hash,
            build_script,
            test_script,
            output_dir,
            "A",
            sanitizer_names,
            True,
        )
        source_name = cp_source_names[0][1]
        # TODO: if chopper result is None, just give the latest commit for now
        if chopper_result is None:
            chopper_result = curr_commit_hash
    else:
        repositories = list(enumerate(cp_source_names))
        repositories.sort(
            key=lambda x: sum(1 for _ in Repo(x[1][0]).iter_commits()), reverse=True
        )
        print("Starting bisect for multi repo case ...")
        for repo in repositories:
            print(f"Starting bisect for repo {repo[1][1]} ...")
            cp_src = repo[1][0]
            curr_commit_hash = get_curr_commit_hash(cp_src)
            repo_stash_checkout(cp_src, curr_commit_hash)
            chopper_result: str | None = run_bisect_linear(
                cp_src,
                cp_path,
                curr_commit_hash,
                build_script,
                test_script,
                output_dir,
                "A",
                sanitizer_names,
                False,
            )
            repo_stash_checkout(cp_src, curr_commit_hash)
            if chopper_result is not None:
                source_name = repo[1][1]
                break
        else:
            chopper_result = get_curr_commit_hash(cp_source_names[0][0])
            source_name = cp_source_names[0][1]

    print("\n\n")
    # NOTE: chopper final result is here
    print((chopper_result, source_name))
    with open(output_path, "w") as f:
        f.write(f"{chopper_result}\n{source_name}")
    repo_stash_checkout(cp_src, curr_commit_hash)


if __name__ == "__main__":
    """
    Entry of the Chopper tool.
    """

    bug_info_json_path = sys.argv[1]
    output_path = sys.argv[2]
    try:
        with open(bug_info_json_path, "r") as bug_info_json_file:
            bug_info = json.load(bug_info_json_file)
            main(bug_info, output_path)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        print(f"Error: {e}")
        sys.exit(1)
