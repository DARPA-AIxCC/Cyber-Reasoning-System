import os
from app import utilities, definitions, emitter, partitioner, values


def run_test_script(script_path, patch_file):
    if not script_path:
        return False
    script_command = f"bash {script_path}"
    log_file_name = script_path.split("/")[-1] + ".log"
    log_path = f"{definitions.DIR_LOGS}/{log_file_name}"
    cur_dir = os.getcwd()
    os.chdir(values.CONF_SOURCE_DIR)
    if not os.path.isfile(log_path):
        open(log_path, "w")
    with open(log_path, "a") as log_file:
        log_file.writelines([f"PATCH FILE: {patch_file}\n==================\n"])
        log_file.close()
    status = utilities.execute_command(script_command, output_log=open(log_path, "a"))
    is_passing = status == 0
    os.chdir(cur_dir)
    return is_passing


def run_test_oracle(test_oracle, failing_test_list, patch_file):
    is_passing = True
    log_name = "oracle.log"
    log_path = f"{definitions.DIR_LOGS}/{log_name}"
    if not os.path.isfile(log_path):
        open(log_path, "w")
    with open(log_path, "a") as log_file:
        log_file.writelines([f"PATCH FILE: {patch_file}\n==================\n"])
        log_file.close()
    cur_dir = os.getcwd()
    os.chdir(values.CONF_SOURCE_DIR)
    for test_id in failing_test_list:
        script_command = f"bash {test_oracle} {test_id}"
        status = utilities.execute_command(
            script_command, output_log=open(log_path, "a")
        )
        if status != 0:
            is_passing = False
            break
    os.chdir(cur_dir)
    return is_passing


def test_patched_binary(binary_path, test_oracle, test_id_list, patch_id=None):
    is_valid = True
    for test_id in test_id_list:
        test_command = "cd {3}; {0} {1} {2}".format(
            test_oracle, test_id, binary_path, definitions.DIRECTORY_LIB
        )
        result = utilities.execute_command(test_command)
        if patch_id:
            trace_file = "/tmp/p{0}.trace".format(patch_id)
            save_file = definitions.DIRECTORY_OUTPUT + "/p{0}-t{0}.trace".format(
                patch_id, test_id
            )
            utilities.execute_command("cp {0} {1}".format(trace_file, save_file))
        if int(result) != 0:
            is_valid = False
            break
    return is_valid


def generate_patch_signature(
    binary_path, test_oracle, test_id, patch_id, timeout, dir_snapshot
):
    signature = None
    output_file_path = dir_snapshot + "/p{0}t{1}.snap.log".format(patch_id, test_id)
    output_file = open(output_file_path, "w")
    gdb_script_path = definitions.FILE_GDB_SNAPSHOT_SCRIPT + "_" + str(patch_id)
    test_command = "PATCH_ID={4} timeout {3} {0} {1} {2}".format(
        test_oracle, test_id, binary_path, timeout, patch_id
    )
    utilities.execute_command(test_command, timeout=timeout, output_log=output_file)
    rename_command = "mv {} {}; mv {} {}".format(
        dir_snapshot + "/before.snapshot",
        dir_snapshot + "/{}_before.snapshot".format(test_id),
        dir_snapshot + "/after.snapshot",
        dir_snapshot + "/{}_after.snapshot".format(test_id),
    )
    utilities.execute_command(rename_command)
    # diff_command = "/bin/bash -c \"diff -u0 "
    # diff_command += "<(hexdump -C {}) ".format(dir_snapshot + "/{}_before.snapshot".format(test_id))
    # diff_command += "<(hexdump -C {}) -d ".format(dir_snapshot + "/{}_after.snapshot".format(test_id))
    # diff_command += "| tail -n +4 > {}\"".format(dir_snapshot + "/{}.snap.diff".format(test_id))
    diff_command = "compare_dump {0} {1} > {2}".format(
        dir_snapshot + "/{}_before.snapshot".format(test_id),
        dir_snapshot + "/{}_after.snapshot".format(test_id),
        dir_snapshot + "/{}.snap.diff".format(test_id),
    )
    utilities.execute_command(diff_command)
    signature_file_path = dir_snapshot + "/{}.sig".format(test_id)
    sign_command = "sha1sum {} | awk '{{print $1}}' > {}".format(
        dir_snapshot + "/{}.snap.diff".format(test_id), signature_file_path
    )
    utilities.execute_command(sign_command)
    with open(signature_file_path, "r") as sig_file:
        signature = sig_file.readline()
    return signature.strip()


def test_gdb_binary(gbd_binary_path, test_oracle, test_id, patch_id, timeout):
    is_valid = True
    output_file_path = "/tmp/p{0}.output".format(patch_id)
    if values.DEFAULT_TAG:
        output_file_path = "/tmp/p{}{}.output".format(values.DEFAULT_TAG, patch_id)
    output_file = open(output_file_path, "w")
    gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_" + str(patch_id)
    test_command = "PATCH_ID={4} timeout {3} {0} {1} {2}".format(
        test_oracle, test_id, gbd_binary_path, timeout, patch_id
    )
    result = utilities.execute_command(
        test_command, timeout=timeout, output_log=output_file
    )
    if int(result) != 0:
        save_err_file = definitions.DIRECTORY_OUTPUT + "/p{0}.err".format(patch_id)
        utilities.execute_command("cp {0} {1}".format(output_file_path, save_err_file))
        is_valid = False
    output = open(output_file_path, "r").readlines()
    check = [l for l in output if any(x in l for x in ["No symbol", "No source"])]
    if check:
        save_err_file = definitions.DIRECTORY_OUTPUT + "/p{0}.err".format(patch_id)
        utilities.execute_command("cp {0} {1}".format(output_file_path, save_err_file))
        is_valid = False
    return is_valid


def test_gdb_binary_suite(test_suite, test_id, patch_id, timeout):
    is_valid = True
    output_file_path = "/tmp/p{0}.output".format(patch_id)
    output_file = open(output_file_path, "w")
    test_command = "COVERAGE=0 PATCH_ID={0} timeout {1} {2} {3} ".format(
        patch_id, timeout, test_suite, test_id
    )
    result = utilities.execute_command(
        test_command, timeout=timeout, output_log=output_file
    )
    if int(result) != 0:
        save_err_file = definitions.DIRECTORY_OUTPUT + "/p{0}.err".format(patch_id)
        utilities.execute_command("cp {0} {1}".format(output_file_path, save_err_file))
        is_valid = False
    output = open(output_file_path, "r").readlines()
    check = [l for l in output if any(x in l for x in ["No symbol"])]
    if check:
        save_err_file = definitions.DIRECTORY_OUTPUT + "/p{0}.err".format(patch_id)
        utilities.execute_command("cp {0} {1}".format(output_file_path, save_err_file))
        is_valid = False
    return is_valid
