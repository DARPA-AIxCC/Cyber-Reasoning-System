import multiprocessing as mp
from multiprocessing import TimeoutError
from functools import partial
from app import (
    gdb,
    e9patch,
    compiler,
    utilities,
    values,
    emitter,
    tracer,
    coverage,
    distance,
)
from multiprocessing.dummy import Pool as ThreadPool
import threading
import time
import os
import sys
import re


def mute():
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")


pool = mp.Pool(mp.cpu_count(), initializer=mute)
result_list = []


def collect_result(result):
    global result_list
    result_list.append(result)


def collect_result_timeout(result):
    global result_list, expected_count
    result_list.append(result)
    if len(result_list) == expected_count:
        pool.terminate()


def collect_result_one(result):
    global result_list, found_one
    result_list.append(result)
    if result[0] is True:
        found_one = True
        pool.terminate()


def abortable_worker(func, *args, **kwargs):
    default_value = kwargs.get("default", None)
    index = kwargs.get("index", None)
    p = ThreadPool(1)
    res = p.apply_async(func, args=args)
    try:
        out = res.get(values.DEFAULT_TIMEOUT_SAT)
        return out
    except TimeoutError:
        emitter.warning("\t[warning] timeout raised on a thread")
        return default_value, index


def validate_patch_list_gdb(
    patch_list, binary_path, test_oracle, test_id_list, dir_snapshot
):
    global pool, result_list
    result_list = []
    binary_orig = binary_path
    valid_patch_list = []
    invalid_patch_list = []
    compile_list = []
    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            is_valid = False
            patch_info = patch_list[patch_id]
            fragment_list, _, _, req_compile, dir_cluster = patch_info
            if req_compile:
                compile_list.append(patch_id)
                continue
            result_list.append(
                gdb.validate_patch(
                    patch_id,
                    binary_path,
                    test_oracle,
                    test_id_list,
                    dir_snapshot,
                    patch_info,
                )
            )
    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        lock = None
        for patch_id in patch_list:
            is_valid = False
            patch_info = patch_list[patch_id]
            fragment_list, _, _, req_compile, dir_cluster = patch_info
            if req_compile:
                compile_list.append(patch_id)
                continue
            pool.apply_async(
                gdb.validate_patch,
                args=(
                    patch_id,
                    binary_path,
                    test_oracle,
                    test_id_list,
                    dir_snapshot,
                    patch_info,
                ),
                callback=collect_result,
            )
        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    for result in result_list:
        patch_id, is_valid, test_count = result
        if is_valid:
            valid_patch_list.append(patch_id)
        else:
            invalid_patch_list.append(patch_id)
        values.COUNT_TESTS = values.COUNT_TESTS + test_count
    return valid_patch_list, invalid_patch_list, compile_list


def validate_patch_list_e9(patch_list, binary_path, test_oracle, test_id_list):
    global pool, result_list
    result_list = []
    valid_patch_list = []
    invalid_patch_list = []
    compile_list = []
    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            is_valid = False
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            fragment_list, _, _, req_compile = patch_list[patch_id]
            if req_compile:
                compile_list.append(patch_id)
                continue
            result_list.append(
                e9patch.validate_patch(
                    patch_id, fragment_list[0], binary_path, test_oracle, test_id_list
                )
            )
    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        lock = None
        for patch_id in patch_list:
            is_valid = False
            fragment_list, _, _, req_compile, _ = patch_list[patch_id]
            if req_compile:
                compile_list.append(patch_id)
                continue
            pool.apply_async(
                e9patch.validate_patch,
                args=(
                    patch_id,
                    fragment_list[0],
                    binary_path,
                    test_oracle,
                    test_id_list,
                ),
                callback=collect_result,
            )
        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    for result in result_list:
        patch_id, is_valid = result
        if is_valid:
            valid_patch_list.append(patch_id)
        else:
            invalid_patch_list.append(patch_id)
    return valid_patch_list, invalid_patch_list, compile_list


def validate_patch_list_compile(patch_list, binary_path, test_oracle, test_id_list):
    global pool, result_list
    result_list = []
    high_quality_list = []
    correct_list = []
    plausible_list = []
    fix_fail_list = []
    incorrect_list = []
    invalid_list = []
    failed_list = []
    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            is_valid = False
            _, src_file, patch_file, req_compile, _ = patch_list[patch_id]
            emitter.normal(f"\t\t\tevaluating patch {patch_file}")
            result_list.append(
                compiler.validate_patch(
                    patch_id,
                    src_file,
                    patch_file,
                    binary_path,
                    test_oracle,
                    test_id_list,
                )
            )
    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        lock = None
        for patch_id in patch_list:
            is_valid = False
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            _, src_file, patch_file, req_compile = patch_list[patch_id]
            pool.apply_async(
                compiler.validate_patch,
                args=(
                    patch_id,
                    src_file,
                    patch_file,
                    binary_path,
                    test_oracle,
                    test_id_list,
                ),
                callback=collect_result,
            )
        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    for result in result_list:
        patch_id = result[0]
        if not result[1]:
            failed_list.append(patch_id)
        elif not result[2]:
            invalid_list.append(patch_id)
        elif not result[3]:
            incorrect_list.append(patch_id)
        elif not result[4]:
            fix_fail_list.append(patch_id)
        elif not result[5]:
            plausible_list.append(patch_id)
        elif not result[6]:
            correct_list.append(patch_id)
        elif result[6]:
            high_quality_list.append(patch_id)
        else:
            failed_list.append(patch_id)
    return (
        failed_list,
        invalid_list,
        incorrect_list,
        fix_fail_list,
        plausible_list,
        correct_list,
        high_quality_list,
    )


def trace_patch_list_gdb(patch_list, test_oracle, test_id_list, binary_path):
    global pool, result_list
    result_list = []
    trace_info = dict()
    if values.DEFAULT_TRACE_MODE == "e9":
        binary_path = e9patch.enable_tracing(binary_path)
    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            fragment_list, _, _, req_compile, _ = patch_list[patch_id]
            if values.DEFAULT_TRACE_MODE == "gdb":
                result_list.append(
                    tracer.trace_gdb(
                        test_oracle, test_id_list, patch_id, fragment_list, binary_path
                    )
                )
            elif values.DEFAULT_TRACE_MODE == "e9":
                result_list.append(
                    tracer.trace_e9(
                        test_oracle, test_id_list, patch_id, fragment_list, binary_path
                    )
                )
    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        for patch_id in patch_list:
            fragment_list, _, _, req_compile, _ = patch_list[patch_id]
            if values.DEFAULT_TRACE_MODE == "gdb":
                pool.apply_async(
                    tracer.trace_gdb,
                    args=(
                        test_oracle,
                        test_id_list,
                        patch_id,
                        fragment_list,
                        binary_path,
                    ),
                    callback=collect_result,
                )
            elif values.DEFAULT_TRACE_MODE == "e9":
                pool.apply_async(
                    tracer.trace_e9,
                    args=(
                        test_oracle,
                        test_id_list,
                        patch_id,
                        fragment_list,
                        binary_path,
                    ),
                    callback=collect_result,
                )
        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    for result in result_list:
        patch_id, trace_list = result
        trace_info[patch_id] = trace_list

    original_trace = dict()
    if values.DEFAULT_TRACE_MODE == "gdb":
        original_trace = tracer.trace_gdb(
            test_oracle, test_id_list, None, None, binary_path
        )
    elif values.DEFAULT_TRACE_MODE == "e9":
        original_trace = tracer.trace_e9(
            test_oracle, test_id_list, None, None, binary_path
        )
    trace_info["orig"] = original_trace[1]
    return trace_info


def coverage_patch_list_gdb(patch_list, test_oracle, test_id_list, binary_path):
    global pool, result_list
    result_list = []
    coverage_info = dict()
    binary_path = e9patch.enable_coverage(binary_path)
    timeout = values.DEFAULT_TEST_TIMEOUT
    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            fragment_list, _, _, req_compile, _ = patch_list[patch_id]
            if binary_path:
                result_list.append(
                    coverage.coverage_e9(
                        test_oracle, test_id_list, patch_id, binary_path
                    )
                )
            else:
                result_list.append(
                    coverage.coverage_e9_suite(
                        test_oracle, test_id_list, patch_id, timeout
                    )
                )

    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        for patch_id in patch_list:
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            fragment_list, _, _, req_compile, _ = patch_list[patch_id]
            if binary_path:
                pool.apply_async(
                    coverage.coverage_e9,
                    args=(test_oracle, test_id_list, patch_id, binary_path),
                    callback=collect_result,
                )
            else:
                pool.apply_async(
                    coverage.coverage_e9_suite,
                    args=(test_oracle, test_id_list, patch_id, timeout),
                    callback=collect_result,
                )

        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    for result in result_list:
        patch_id, coverage_list = result
        coverage_info[patch_id] = coverage_list
    # collect coverage of original program
    if binary_path:
        original_program_coverage = coverage.coverage_e9(
            test_oracle, test_id_list, "orig", binary_path
        )
    else:
        original_program_coverage = coverage.coverage_e9_suite(
            test_oracle, test_id_list, "orig", timeout
        )
    coverage_info["orig"] = original_program_coverage[1]
    return coverage_info


def compute_patch_vectors(patch_list, coverage_info, trace_info, edit_distance_info):
    global pool, result_list
    result_list = []
    # orig_trace = trace_info["orig"]
    orig_trace = None
    orig_coverage = coverage_info["orig"]

    if values.DEFAULT_EXEC_MODE in ["sequential"]:
        for patch_id in patch_list:
            satisfied = utilities.check_budget(values.DEFAULT_TIMEOUT)
            if satisfied:
                emitter.warning(
                    "\t[warning] ending due to timeout of "
                    + str(values.DEFAULT_TIMEOUT)
                    + " minutes"
                )
                break

            # p_trace = trace_info[patch_id]
            p_coverage = coverage_info[patch_id]
            p_edit = edit_distance_info[patch_id]
            p_trace = None
            result_list.append(
                distance.compute_score_vector(
                    patch_id, p_trace, p_coverage, orig_trace, orig_coverage, p_edit
                )
            )

    else:
        emitter.normal("\t\t\tstarting parallel computing")
        pool = mp.Pool(mp.cpu_count(), initializer=mute)
        for patch_id in patch_list:
            # p_trace = trace_info[patch_id]
            p_trace = None
            p_coverage = coverage_info[patch_id]
            p_edit = edit_distance_info[patch_id]
            pool.apply_async(
                distance.compute_score_vector,
                args=(patch_id, p_trace, p_coverage, orig_trace, orig_coverage, p_edit),
                callback=collect_result,
            )
        pool.close()
        emitter.normal("\t\t\twaiting for thread completion")
        pool.join()
    return result_list
