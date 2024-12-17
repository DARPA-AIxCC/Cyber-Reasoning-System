from app import definitions, values, emitter, parallel, utilities, gdb, e9patch
import os


def process_trace(trace_file_path):
    trace_list = []
    with open(trace_file_path, "r") as trace_file:
        content = trace_file.readlines()
        trace_list.append(content[0].strip().replace("\n", ""))
        for line in content[1:]:
            if line[:2] != "00":
                continue
            line.strip().replace("\n", "")
            if line != trace_list[-1]:
                trace_list.append(line)
    return trace_list


def trace_e9(test_oracle, test_id_list, patch_id, fragment_list, binary_path):
    trace_list = dict()
    gdb_script_path = None
    if patch_id:
        gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_" + str(patch_id)
        # frontend_path = definitions.FILE_GDB_FRONTEND + "_" + str(patch_id)
        frontend_path = os.path.dirname(test_oracle) + "/gdb_frontend"
        gdb.prepare_frontend(frontend_path, gdb_script_path, binary_path)
        trace_file = "/tmp/p{0}.trace".format(patch_id)
    else:
        trace_file = "/tmp/p{0}.trace".format("orig")
        frontend_path = binary_path

    for test_id in test_id_list:
        if gdb_script_path:
            test_command = "PATCH_ID={4} timeout -k 2s 10s {0} {1} {2} 2> {3}".format(
                test_oracle, test_id, frontend_path, trace_file, patch_id
            )
        else:
            test_command = "timeout -k 2s 10s {0} {1} {2} 2> {3}".format(
                test_oracle, test_id, frontend_path, trace_file
            )

        utilities.execute_command(test_command)
        save_file = definitions.DIRECTORY_OUTPUT + "/p{0}-t{1}.trace".format(
            patch_id, test_id
        )
        utilities.execute_command("cp {0} {1}".format(trace_file, save_file))
        trace_list[test_id] = process_trace(save_file)
    return patch_id, trace_list


def trace_gdb(test_oracle, test_id_list, patch_id, fragment_list, binary_path):
    trace_list = dict()
    gdb_script_path = None
    if patch_id:
        trace_file = "/tmp/p{0}.trace".format(patch_id)
        gdb_script_path = definitions.FILE_GDB_PATCH_SCRIPT + "_" + str(patch_id)
        frontend_path = definitions.FILE_GDB_FRONTEND + "_" + str(patch_id)
        gdb.enable_tracing(fragment_list, gdb_script_path, trace_file)
    else:
        trace_file = "/tmp/p{0}.trace".format("orig")
        frontend_path = binary_path
    for test_id in test_id_list:
        if gdb_script_path:
            test_command = "PATCH_ID={3} timeout -k 2s 10s {0} {1} {2}".format(
                test_oracle, test_id, frontend_path, patch_id
            )
        else:
            test_command = "timeout -k 2s 10s {0} {1} {2}".format(
                test_oracle, test_id, frontend_path
            )
        utilities.execute_command(test_command)
        save_file = definitions.DIRECTORY_OUTPUT + "/p{0}-t{1}.trace".format(
            patch_id, test_id
        )
        utilities.execute_command(
            'cat {0} | grep "#0 " > {1}'.format(trace_file, save_file)
        )
        trace_list[test_id] = process_trace(save_file)
    return patch_id, trace_list
