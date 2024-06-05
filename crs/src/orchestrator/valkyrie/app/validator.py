import shutil
from app import definitions, values, parallel, emitter, writer


def validate_patches(patch_list, test_id_list, test_oracle, binary_path, dir_snapshot):
    emitter.sub_sub_title("Validating Patches")
    emitter.normal("\t\tevaluating patches")
    classified_list = []
    if values.DEFAULT_PATCH_MODE == definitions.VALUE_OPERATE_MODE_GDB:
        classified_list = parallel.validate_patch_list_gdb(
            patch_list, binary_path, test_oracle, test_id_list, dir_snapshot
        )
    elif values.DEFAULT_PATCH_MODE == definitions.VALUE_OPERATE_MODE_REWRITE:
        classified_list = parallel.validate_patch_list_e9(
            patch_list, binary_path, test_oracle, test_id_list
        )
    elif values.DEFAULT_PATCH_MODE == definitions.VALUE_OPERATE_MODE_COMPILE:
        classified_list = parallel.validate_patch_list_compile(
            patch_list, binary_path, test_oracle, test_id_list
        )

    return classified_list
