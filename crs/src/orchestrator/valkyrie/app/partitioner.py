import os.path
from collections import OrderedDict
from app import distance, writer, definitions, gdb, emitter, tester, values


def update_partition_dir(patch_list, dir_partition):
    emitter.sub_sub_title("Collecting Location Info")
    emitter.normal("\t\tanalysing patches for fix locations")
    updated_list = OrderedDict()
    for patch_id in patch_list:
        fragment_list, src_file, patch_file, req_compile = patch_list[patch_id]
        location_id = None
        for fragment in fragment_list:
            break_point, _, _ = fragment
            if not location_id:
                location_id = (
                    dir_partition
                    + "/"
                    + str(break_point).replace("/", "").replace(":", "_").lower()
                )
            else:
                location_id = location_id + "_" + str(break_point)
        updated_list[patch_id] = (
            fragment_list,
            src_file,
            patch_file,
            req_compile,
            location_id,
        )
    return updated_list


def get_patch_signature(
    patch_info, patch_id, base_dir_snapshot, binary_path, test_oracle, test_id
):
    gdb_script_path = definitions.FILE_GDB_SNAPSHOT_SCRIPT + "_" + str(patch_id)
    fragment_list, _, _, req_compile, _ = patch_info
    dir_snapshot = base_dir_snapshot + "/" + str(patch_id)
    if not os.path.isdir(dir_snapshot):
        os.system("mkdir -p {}".format(dir_snapshot))
    gdb.prepare_snapshot_script(fragment_list, gdb_script_path, dir_snapshot)
    # frontend_path = definitions.FILE_GDB_FRONTEND + "_" + str(patch_id) + "_snapshot"
    frontend_path = os.path.dirname(binary_path) + "/gdb_frontend_snapshot"
    gdb.prepare_frontend(frontend_path, gdb_script_path, binary_path)
    signature = tester.generate_patch_signature(
        frontend_path,
        test_oracle,
        test_id,
        patch_id,
        values.DEFAULT_TEST_TIMEOUT,
        dir_snapshot,
    )
    return signature
