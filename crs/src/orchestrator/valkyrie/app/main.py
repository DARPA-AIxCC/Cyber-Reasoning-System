import sys
import json
import subprocess
import os
import shutil
import traceback
import signal
import time
from app import (
    emitter,
    logger,
    definitions,
    values,
    tracer,
    configuration,
    loader,
    validator,
    utilities,
    ranker,
    writer,
    partitioner,
)


start_time = 0
end_time = 0


def create_directories():
    if not os.path.isdir(definitions.DIR_LOGS):
        os.makedirs(definitions.DIR_LOGS)
    if not os.path.isdir(definitions.DIR_RESULT):
        os.makedirs(definitions.DIR_RESULT)
    if not os.path.isdir(definitions.DIR_LOGS):
        os.makedirs(definitions.DIR_LOGS)
    if not os.path.isdir(definitions.DIRECTORY_OUTPUT):
        os.makedirs(definitions.DIRECTORY_OUTPUT)


def timeout_handler(signum, frame):
    emitter.error("TIMEOUT Exception")
    raise Exception("end of time")


def shutdown(signum, frame):
    global stop_event
    emitter.warning("Exiting due to Terminate Signal")
    stop_event.set()
    raise SystemExit


def bootstrap(arg_list):
    emitter.sub_title("Bootstrapping tool")
    configuration.read_arg(arg_list)
    configuration.read_conf_file()
    configuration.validate_configuration()
    values.CONF_ARG_PASS = True
    configuration.update_configuration()
    configuration.check_dependencies()
    configuration.print_configuration()


def print_class(class_name, patch_class):
    if patch_class:
        emitter.normal(f"\t\t found {len(patch_class)} number of {class_name} patches")
        for p in patch_class:
            emitter.highlight(f"\t\t\t{p}")


def copy_patch(patch_list, dir_class):
    for patch_id in patch_list:
        tool_name, patch_index = patch_id.split(":")
        patch_file = f"{values.CONF_PATCH_DIR}/{tool_name}/{patch_index}"
        copy_command = f"cp {patch_file} {dir_class}/{tool_name}-{patch_index}"
        utilities.execute_command(copy_command)


def run():
    emitter.sub_title("Initializing setup")
    classified_list = ([], [], [], [], [], [], [])
    patch_list = []
    if values.CONF_CLONE:
        src_dir = values.CONF_SOURCE_DIR
        clone_dir = f"{definitions.DIR_EXPERIMENT}/{hex(int(time.time()))}"
        clone_command = f"cp -rf {src_dir} {clone_dir}"
        utilities.execute_command(clone_command)
        values.CONF_SOURCE_DIR = clone_dir
    if values.CONF_PATCH_DIR:
        patch_list = loader.load_patch_list(values.CONF_PATCH_DIR)
        if patch_list:
            values.COUNT_INITIAL = len(patch_list)
            snapshot_dir, partition_dir = utilities.create_artefact_dirs(
                values.CONF_PATCH_DIR
            )
            emitter.sub_title("Classifying Patches")
            patch_list = partitioner.update_partition_dir(patch_list, partition_dir)
            binary_path = values.CONF_BIN_PATH
            test_oracle = values.CONF_TEST_ORACLE
            if values.CONF_TEST_SUITE:
                test_oracle = values.CONF_TEST_SUITE
                binary_path = None
            classified_list = validator.validate_patches(
                patch_list,
                values.CONF_TEST_ID_LIST,
                test_oracle,
                binary_path,
                snapshot_dir,
            )
            # filtered_patch_list = dict()
            # values.COUNT_VALID = len(valid_id_list)
            # for patch_id in valid_id_list:
            #     filtered_patch_list[patch_id] = patch_list[patch_id]
            # if valid_id_list:
            #     writer.write_filtered_patches(valid_id_list, values.CONF_PATCH_DIR, valid_dir)
            #     if not values.DEFAULT_ONLY_VALIDATE:
            #         ranked_list = ranker.rank_patches(filtered_patch_list, values.CONF_TEST_ID_LIST,
            #                                           test_oracle, values.CONF_BIN_PATH)
            #         writer.write_ranked_patches(ranked_list, values.CONF_PATCH_DIR, ranked_dir)
        else:
            emitter.warning("[warning] no patch detected, nothing to do")
    elif values.CONF_PATCH_FILE:
        values.COUNT_INITIAL = 1
        patch_index, fragment_list, src_file, patch_file, req_compile, is_unhandled = loader.load_patch_file(
            values.CONF_PATCH_FILE
        )
        patch_dir = os.path.dirname(values.CONF_PATCH_FILE)
        snapshot_dir, partition_dir = utilities.create_artefact_dirs(patch_dir)
        patch_list = {patch_index: (fragment_list, src_file, patch_file, req_compile)}
        patch_list = partitioner.update_partition_dir(patch_list, partition_dir)
        binary_path = values.CONF_BIN_PATH
        test_oracle = values.CONF_TEST_ORACLE
        if values.CONF_TEST_SUITE:
            test_oracle = values.CONF_TEST_SUITE
            binary_path = None
        classified_list = validator.validate_patches(
            patch_list, values.CONF_TEST_ID_LIST, test_oracle, binary_path, snapshot_dir
        )
        # filtered_patch_list = dict()
        # values.COUNT_VALID = len(valid_id_list)
        # for patch_id in valid_id_list:
        #     filtered_patch_list[patch_id] = patch_list[patch_id]
        # if valid_id_list:
        #     writer.write_filtered_patches(valid_id_list, patch_dir, valid_dir)
        #     if not values.DEFAULT_ONLY_VALIDATE:
        #         ranked_list = ranker.rank_patches(filtered_patch_list, values.CONF_TEST_ID_LIST,
        #                                           values.CONF_TEST_ORACLE, values.CONF_BIN_PATH)
        #         writer.write_ranked_patches(ranked_list, patch_dir, ranked_dir)
    else:
        emitter.warning("[warning] no patch detected, nothing to do")

    patch_categories = [
        "incorrect",
        "invalid",
        "failure-fixing",
        "plausible",
        "correct",
        "high_quality",
    ]

    for _dir in patch_categories:
        mkdir_command = f"mkdir -p {values.CONF_OUTPUT_DIR}/{_dir}"
        utilities.execute_command(mkdir_command)
    failed_list = classified_list[0]
    invalid_list = classified_list[1]
    incorrect_list = classified_list[2]
    fix_fail_list = classified_list[3]
    plausible_list = classified_list[4]
    correct_list = classified_list[5]
    high_quality_list = classified_list[6]

    if failed_list:
        values.COUNT_INVALID = len(failed_list)
        copy_patch(failed_list, f"{values.CONF_OUTPUT_DIR}/invalid")
        print_class("failed to apply", failed_list)
    if invalid_list:
        values.COUNT_BUILD_FAIL = len(invalid_list)
        copy_patch(invalid_list, f"{values.CONF_OUTPUT_DIR}/invalid")
        print_class("failed to compile", invalid_list)
    if incorrect_list:
        values.COUNT_INCORRECT = len(incorrect_list)
        copy_patch(incorrect_list, f"{values.CONF_OUTPUT_DIR}/incorrect")
        print_class("incorrect", incorrect_list)
    if fix_fail_list:
        values.COUNT_FIX_FAIL = len(fix_fail_list)
        copy_patch(fix_fail_list, f"{values.CONF_OUTPUT_DIR}/failure-fixing")
        print_class("fixed failing", fix_fail_list)
    if plausible_list:
        values.COUNT_PLAUSIBLE = len(plausible_list)
        copy_patch(plausible_list, f"{values.CONF_OUTPUT_DIR}/plausible")
        print_class("plausible but not correct", plausible_list)
    if correct_list:
        values.COUNT_CORRECT = len(correct_list)
        copy_patch(correct_list, f"{values.CONF_OUTPUT_DIR}/correct")
        print_class("correct", correct_list)
    if high_quality_list:
        values.COUNT_HQ = len(high_quality_list)
        copy_patch(high_quality_list, f"{values.CONF_OUTPUT_DIR}/high_quality")
        print_class("high quality", high_quality_list)

    patch_result = []
    for patch_id in patch_list:
        _class = ""
        if patch_id in failed_list:
            _class = "invalid patch"
        elif patch_id in invalid_list:
            _class = "cannot build"
        elif patch_id in incorrect_list:
            _class = "incorrect patch"
        elif patch_id in fix_fail_list:
            _class = "fixed failing"
        elif patch_id in plausible_list:
            _class = "pass public"
        elif patch_id in correct_list:
            _class = "pass private"
        elif patch_id in high_quality_list:
            _class = "pass adversarial"
        patch_result.append((patch_id, _class))
    writer.write_as_json(patch_result, f"{values.CONF_OUTPUT_DIR}/result.json")

    if values.CONF_PURGE:
        if definitions.DIR_EXPERIMENT in values.CONF_SOURCE_DIR:
            purge_command = f"rm -rf {values.CONF_SOURCE_DIR}"
            utilities.execute_command(purge_command)

    #
    # if compilation_list:
    #     # print("Compilation Required")
    #     # print("Count: " + str(len(compilation_list)))
    #     # sorted_list = sorted([int(x) for x in compilation_list])
    #     # print(sorted_list)
    #     values.COUNT_COMPILE = len(compilation_list)
    #     writer.write_filtered_patches(compilation_list, dir_patch, dir_error)
    # if invalid_list:
    #     # print("Invalid List")
    #     # print("Count: " + str(len(invalid_list)))
    #     values.COUNT_INVALID = len(invalid_list)
    #     sorted_reject_list = sorted(invalid_list)
    #     # print(sorted_reject_list)
    #     possible_issues = writer.write_invalid_patch_list(sorted_reject_list, definitions.FILE_INVALID_LIST)
    #     values.COUNT_UNHANDLED = len(possible_issues)
    #     if possible_issues:
    #         emitter.warning("\t\t[warning] Possible Issues")
    #         emitter.warning("\t\t{}".format(",".join(possible_issues)))
    #     writer.write_filtered_patches(invalid_list, dir_patch, dir_invalid)
    #
    # # if valid_list:
    #     # print("Valid List")
    #     # print("Count: " + str(len(valid_list)))
    #     # sorted_valid_list = sorted([int(x) for x in valid_list])
    #     # print(sorted_valid_list)
    # emitter.normal("\t\t found {0} number of valid patches".format(len(valid_list)))


def main():
    import sys

    is_error = False
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.signal(signal.SIGTERM, shutdown)
    start_time = time.time()
    create_directories()
    logger.create()
    time_info = dict()
    try:
        emitter.title("Starting " + values.TOOL_NAME + " (Patch Verification Tool) ")
        bootstrap(sys.argv[1:])
        run()
    except SystemExit as e:
        total_duration = format((time.time() - start_time) / 60, ".3f")
        time_info[definitions.KEY_DURATION_TOTAL] = total_duration
    except KeyboardInterrupt as e:
        total_duration = format((time.time() - start_time) / 60, ".3f")
        time_info[definitions.KEY_DURATION_TOTAL] = total_duration
    except Exception as e:
        is_error = True
        emitter.error("Runtime Error")
        emitter.error(str(e))
        logger.error(traceback.format_exc())
    finally:
        total_duration = format((time.time() - start_time) / 60, ".3f")
        time_info[definitions.KEY_DURATION_TOTAL] = total_duration
        values.RESULT["duration"] = total_duration
        values.RESULT["valid-count"] = values.COUNT_VALID
        values.RESULT["execution-count"] = values.COUNT_TESTS
        values.RESULT["invalid-count"] = values.COUNT_INVALID
        values.RESULT["unhandled-count"] = values.COUNT_UNHANDLED
        emitter.end(time_info, is_error)
        logger.end(time_info, is_error)
        writer.write_as_json(values.RESULT, definitions.FILE_RESULT_JSON)
        if is_error:
            exit(1)
        exit(0)
