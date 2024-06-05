import os
from app import definitions, values, emitter, parallel, utilities, gdb, e9patch


def process_coverage(coverage_file_path):
    coverage_info = dict()
    with open(coverage_file_path, "r") as trace_file:
        content = trace_file.readlines()
        for line in content:
            address, count = line.strip().replace("\n", "").split(":")
            coverage_info[address] = count
    return coverage_info


def coverage_e9(test_oracle, test_id_list, patch_id, binary_path):
    coverage_info = dict()
    gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_coverage"
    if patch_id == "orig":
        os.system("touch {}".format(gdb_script_path))
    # frontend_path = definitions.FILE_GDB_FRONTEND + "_coverage"
    frontend_path = os.path.dirname(binary_path) + "/gdb_frontend_coverage"
    coverage_file = "/tmp/p{0}.coverage".format(patch_id)
    gdb.prepare_frontend_coverage(
        frontend_path, gdb_script_path, binary_path, coverage_file
    )
    for test_id in test_id_list:
        test_command = "PATCH_ID={3} timeout -k 2s 10s {0} {1} {2}".format(
            test_oracle, test_id, frontend_path, patch_id
        )
        utilities.execute_command(test_command)
        save_file = definitions.DIRECTORY_OUTPUT + "/p{0}-t{1}.coverage".format(
            patch_id, test_id
        )
        utilities.execute_command("cp {0} {1}".format(coverage_file, save_file))
        coverage_info[test_id] = process_coverage(coverage_file)
    return patch_id, coverage_info


def coverage_e9_suite(test_suite, test_id_list, patch_id, timeout):
    coverage_info = dict()
    gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_coverage"
    if patch_id == "orig":
        os.system("touch {}".format(gdb_script_path))
    coverage_file = "/tmp/p{0}.coverage".format(patch_id)
    for test_id in test_id_list:
        output_file_path = "/tmp/p{0}t{1}.output".format(patch_id, test_id)
        output_file = open(output_file_path, "w")
        coverage_command = "COVERAGE=1 PATCH_ID={0} timeout {1} {2} {3} ".format(
            patch_id, timeout, test_suite, test_id
        )
        utilities.execute_command(
            coverage_command, timeout=timeout, output_log=output_file
        )
        save_file = definitions.DIRECTORY_OUTPUT + "/p{0}-t{1}.coverage".format(
            patch_id, test_id
        )
        utilities.execute_command("cp {0} {1}".format(coverage_file, save_file))
        coverage_info[test_id] = process_coverage(coverage_file)
    return patch_id, coverage_info
