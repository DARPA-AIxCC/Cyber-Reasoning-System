import os
import multiprocessing as mp
from app import (
    utilities,
    definitions,
    interpreter,
    values,
    tester,
    emitter,
    partitioner,
)
from multiprocessing.dummy import Pool as ThreadPool


def enable_tracing(fragment_list, gdb_script_path, tracing_file):
    with open(gdb_script_path, "r") as script_file:
        script_lines = script_file.readlines()
        script_file.close()
    script_lines.insert(0, "set logging redirect on\n")
    script_lines.insert(0, "set logging file {}\n".format(tracing_file))
    script_lines.insert(0, "set logging overwrite on\n")
    script_lines.insert(0, "set logging on\n")
    script_lines = script_lines[:-1]
    for fragment in fragment_list:
        break_point, jump_point, patch_content = fragment
        if jump_point:
            script_lines.append("break {}\n".format(jump_point))
        else:
            script_lines.append("tbreak +1\n")
        script_lines.append("commands\n")
        script_lines.append("silent\n")
        script_lines.append("while 1\n")
        script_lines.append("frame\n")
        script_lines.append("step\n")
        script_lines.append("end\n")
        script_lines.append("end\n")
    script_lines.append("run 1\n")
    with open(gdb_script_path, "w+") as script_file:
        script_file.seek(0)
        script_file.writelines(script_lines)
        script_file.truncate()
        script_file.close()
    return


def prepare_snapshot_script(fragment_list, gdb_script_path, dir_snapshot):
    with open(gdb_script_path, "w+") as script_file:
        script_file.truncate()
        script_file.writelines("set pagination off\n")
        script_file.writelines("set disable-randomization on\n")
        script_file.writelines("set breakpoint pending on\n")
        file_before_snapshot = dir_snapshot + "/before.snapshot"
        file_after_snapshot = dir_snapshot + "/after.snapshot"
        for fragment in fragment_list:
            break_point, jump_point, patch_content = fragment
            script_file.writelines(snapshot_command)
            if patch_content:
                gdb_command, _ = interpreter.convert_to_gdb_command(
                    patch_content, break_point, jump_point, file_before_snapshot
                )
                script_file.writelines(gdb_command)
            snapshot_command = "generate-core-file {}\n".format(file_after_snapshot)
            script_file.writelines(snapshot_command)
            script_file.writelines("quit\nend\n")
        script_file.writelines("run 1\n")
        script_file.close()
    return


def prepare_patch_script(fragment_list, gdb_script_path, dir_snapshot):
    with open(gdb_script_path, "w+") as script_file:
        script_file.truncate()
        script_file.writelines("set pagination off\n")
        script_file.writelines("set disable-randomization off\n")
        script_file.writelines("set breakpoint pending on\n")
        if dir_snapshot:
            file_after_snapshot = dir_snapshot + "/location.snapshot"
        for fragment in fragment_list:
            break_point, jump_point, patch_content = fragment
            if patch_content:
                gdb_command, is_iteration = interpreter.convert_to_gdb_command(
                    patch_content, break_point, jump_point, None
                )
            if patch_content:
                script_file.writelines(gdb_command)
            if dir_snapshot:
                snapshot_command = "generate-core-file {}\n".format(file_after_snapshot)
                script_file.writelines(snapshot_command)
            script_file.writelines("end\n")
        script_file.writelines("run 1\n")
        script_file.close()
    return


def prepare_frontend(frontend_path, gdb_script_path, binary_path):
    if not os.path.isfile(frontend_path):
        with open(frontend_path, "w+") as frontend_file:
            frontend_file.truncate()
            frontend_file.writelines("#!/bin/bash\n")
            frontend_file.writelines("patch_id=$PATCH_ID\n")
            frontend_file.writelines("script_file=/tmp/gdb_patch_script_$patch_id\n")
            frontend_file.writelines("if [[ -f $script_file ]];then\n")
            frontend_file.writelines("sed -i '$ d'  $script_file \n")
            frontend_file.writelines('echo "run $@" >> $script_file\n')
            frontend_file.writelines(
                "gdb -return-child-result -batch-silent -x $script_file {0}\n".format(
                    binary_path
                )
            )
            frontend_file.writelines("else\n")
            frontend_file.writelines("{} $@\n".format(binary_path))
            frontend_file.writelines("fi\n")
            frontend_file.close()
        utilities.execute_command("chmod +x {}".format(frontend_path))
    return


def prepare_frontend_coverage(
    frontend_path, gdb_script_path, binary_path, coverage_output
):
    if not os.path.isfile(frontend_path):
        with open(frontend_path, "w+") as frontend_file:
            frontend_file.truncate()
            frontend_file.writelines("#!/bin/bash\n")
            frontend_file.writelines("patch_id=$PATCH_ID\n")
            frontend_file.writelines("script_file=/tmp/gdb_patch_script_$patch_id\n")
            frontend_file.writelines("coverage_file=/tmp/p$patch_id.coverage\n")
            frontend_file.writelines("sed -i '$ d'  $script_file \n")
            frontend_file.writelines('echo "run $@" >> $script_file\n')
            frontend_file.writelines(
                "afl-showmap -m 1234 -o $coverage_file  gdb -return-child-result -batch-silent -x $script_file {0}\n".format(
                    binary_path
                )
            )
            frontend_file.close()
        utilities.execute_command("chmod +x {}".format(frontend_path))
    return


def validate_patch(
    patch_id, binary_path, test_oracle, test_id_list, base_dir_snapshot, patch_info
):
    fragment_list, _, _, req_compile, dir_cluster = patch_info
    timeout = values.DEFAULT_TEST_TIMEOUT
    nested_cluster = dir_cluster
    is_valid = True
    test_count = 0
    is_location_repeated = False
    fail_test_list = []
    if os.path.isdir(dir_cluster):
        if os.path.isfile(dir_cluster + "/LOOP"):
            is_location_repeated = True
    if values.DEFAULT_PARTITION and not is_location_repeated:
        if not os.path.isdir(dir_cluster):
            os.system("mkdir {} > /dev/null 2>&1".format(dir_cluster))
        dir_snapshot = base_dir_snapshot + "/" + str(patch_id)
        if not os.path.isdir(dir_snapshot):
            os.system("mkdir -p {}".format(dir_snapshot))
        for test_id in test_id_list:
            if not is_location_repeated:
                patch_signature = partitioner.get_patch_signature(
                    patch_info,
                    patch_id,
                    base_dir_snapshot,
                    binary_path,
                    test_oracle,
                    test_id,
                )
                if not patch_signature:
                    emitter.warning(
                        "[warning] no signature detected for patch:{0} and test:{1}".format(
                            patch_id, test_id
                        )
                    )
                    utilities.error_exit("[error] cannot find partition")
                nested_cluster += "/" + patch_signature
                if not os.path.isdir(nested_cluster):
                    utilities.execute_command("mkdir {}".format(nested_cluster))
                if os.path.isfile(nested_cluster + "/FAIL"):
                    print("CLUSTER FAIL", patch_signature)
                    is_valid = False
                    break
                elif os.path.isfile(nested_cluster + "/PASS"):
                    continue
                else:
                    test_count = test_count + 1
                    tmp_path = definitions.FILE_GDB_PATCH_SCRIPT
                    gdb_script_path = "_".join([tmp_path, str(patch_id)])
                    if values.DEFAULT_TAG:
                        gdb_script_path = "_".join(
                            [tmp_path, values.DEFAULT_TAG, str(patch_id)]
                        )
                    prepare_patch_script(fragment_list, gdb_script_path, dir_snapshot)
                    if binary_path:
                        frontend_path = os.path.dirname(binary_path) + "/gdb_frontend"
                        prepare_frontend(frontend_path, gdb_script_path, binary_path)
                        is_valid = tester.test_gdb_binary(
                            frontend_path, test_oracle, test_id, patch_id, timeout
                        )
                    else:
                        is_valid = tester.test_gdb_binary_suite(
                            test_oracle, test_id, patch_id, timeout
                        )
                    if not is_valid:
                        fail_test_list.append(test_id)
                    check_snapshot_file = dir_snapshot + "/{}_after.snapshot".format(
                        test_id
                    )
                    latest_snapshot_file = dir_snapshot + "/location.snapshot"
                    diff_command = "compare_dump {0} {1} > {2}".format(
                        check_snapshot_file,
                        latest_snapshot_file,
                        dir_snapshot + "/{}.snap.diff".format(test_id),
                    )
                    is_same = utilities.execute_command(diff_command)
                    if is_same:
                        if not is_valid:
                            utilities.execute_command(
                                "touch {}".format(nested_cluster + "/FAIL")
                            )
                            break
                        utilities.execute_command(
                            "touch {}".format(nested_cluster + "/PASS")
                        )
                    else:
                        utilities.execute_command(
                            "touch {}".format(nested_cluster + "/LOOP")
                        )
            else:
                test_count = test_count + 1
                gdb_script_path = (
                    definitions.FILE_GDB_PATCH_SCRIPT + "_" + str(patch_id)
                )
                prepare_patch_script(fragment_list, gdb_script_path, None)
                if binary_path:
                    frontend_path = os.path.dirname(binary_path) + "/gdb_frontend"
                    prepare_frontend(frontend_path, gdb_script_path, binary_path)
                    is_valid = tester.test_gdb_binary(
                        frontend_path, test_oracle, test_id, patch_id, timeout
                    )
                else:
                    is_valid = tester.test_gdb_binary_suite(
                        test_oracle, test_id, patch_id, timeout
                    )

                if not is_valid:
                    fail_test_list.append(test_id)
                if not is_valid and not values.DEFAULT_COMPLETE_TEST_RUN:
                    break

    else:
        for test_id in test_id_list:
            test_count = test_count + 1
            gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_" + str(patch_id)
            prepare_patch_script(fragment_list, gdb_script_path, None)
            if binary_path:
                frontend_path = os.path.dirname(binary_path) + "/gdb_frontend"
                prepare_frontend(frontend_path, gdb_script_path, binary_path)
                is_valid = tester.test_gdb_binary(
                    frontend_path, test_oracle, test_id, patch_id, timeout
                )
            else:
                is_valid = tester.test_gdb_binary_suite(
                    test_oracle, test_id, patch_id, timeout
                )
            if not is_valid:
                fail_test_list.append(test_id)
            if not is_valid and not values.DEFAULT_COMPLETE_TEST_RUN:
                break
    patch_is_valid = len(fail_test_list) == 0
    return patch_id, patch_is_valid, test_count
