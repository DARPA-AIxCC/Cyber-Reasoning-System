import os
import pathlib
import shutil

from app import utilities, definitions, emitter, tester, values, debugger


def use_diff_patch(src_path, patch_file, is_reverse=False, is_unified=True):
    src_dir = values.CONF_SOURCE_DIR
    if not src_dir:
        src_dir = "/".join(src_path.split("/")[:-1])
    orig_file_list = list(pathlib.Path(src_dir).rglob("*.orig"))

    if values.CONF_SOURCE_DIR and not values.CONF_SOURCE_FILE:
        curr_dir = os.getcwd()
        os.chdir(src_dir)
        source_file = None
        source_file_name = src_path.split("/")[-1]
        list_files = [
            os.path.join(values.CONF_SOURCE_DIR, t)
            for t in list(pathlib.Path(values.CONF_SOURCE_DIR).rglob(source_file_name))
        ]

        for _f in list_files:
            if source_file_name in _f:
                source_file = _f
        if source_file:
            patch_command = f"patch --ignore-whitespace -b {'-u' if is_unified else ''} {'-R' if is_reverse else ''} {source_file} < {patch_file}"
        else:
            patch_command = f"patch --ignore-whitespace -b {'-u' if is_unified else ''} {'-R' if is_reverse else ''} -f -p1 < {patch_file}"
        patch_status = utilities.execute_command(patch_command)
        patch_successful = patch_status == 0
        os.chdir(curr_dir)
    elif values.CONF_SOURCE_FILE and values.CONF_PATCH_DIR:
        curr_dir = os.getcwd()
        os.chdir(src_dir)
        patch_command = f"patch --ignore-whitespace -b {'-u' if is_unified else ''} {'-R' if is_reverse else ''} {values.CONF_SOURCE_FILE} < {patch_file}"
        patch_status = utilities.execute_command(patch_command)
        patch_successful = patch_status == 0
        os.chdir(curr_dir)
    else:
        patch_command = f"patch --ignore-whitespace -b {'-u' if is_unified else ''} {'-R' if is_reverse else ''} {src_path} {patch_file}"
        patch_status = utilities.execute_command(patch_command)
        patch_successful = patch_status == 0

    if not patch_successful:
        new_orig_file_list = list(pathlib.Path(src_dir).rglob("*.orig"))
        backup_list = list(set(new_orig_file_list) - set(orig_file_list))
        for b_file in backup_list:
            utilities.execute_command(f"mv {b_file} {str(b_file).replace('.orig', '')}")
    return patch_successful


def apply_patch(src_path, patch_file, is_unified=True):
    patch_successful = False
    src_dir = values.CONF_SOURCE_DIR
    patch_command = values.CONF_PATCH_COMMAND
    patch_script = values.CONF_PATCH_SCRIPT
    if patch_command:
        cur_dir = os.getcwd()
        os.chdir(src_dir)
        patch_command = str(patch_command).replace("PATCH_FILE", patch_file)
        patch_status = utilities.execute_command(patch_command)
        patch_successful = patch_status == 0
        os.chdir(cur_dir)
    elif patch_script:
        cur_dir = os.getcwd()
        os.chdir(src_dir)
        patch_command = f"{values.CONF_PATCH_SCRIPT} {patch_file}"
        patch_status = utilities.execute_command(patch_command)
        patch_successful = patch_status == 0
        os.chdir(cur_dir)
    else:
        patch_successful = use_diff_patch(src_path, patch_file, False, is_unified)
        if not patch_successful:
            is_unified = False
            patch_successful = use_diff_patch(src_path, patch_file, False, is_unified)
    return patch_successful, is_unified


def reset_patch(src_path, patch_file, is_unified=True):
    reset_successful = False
    src_dir = values.CONF_SOURCE_DIR
    reset_command = values.CONF_RESET_COMMAND
    reset_script = values.CONF_RESET_SCRIPT
    if reset_command:
        cur_dir = os.getcwd()
        os.chdir(src_dir)
        reset_command = str(reset_command).replace("PATCH_FILE", patch_file)
        reset_status = utilities.execute_command(reset_command)
        reset_successful = reset_status == 0
        os.chdir(cur_dir)
    elif reset_script:
        cur_dir = os.getcwd()
        os.chdir(src_dir)
        reset_command = f"{values.CONF_PATCH_SCRIPT} {patch_file}"
        reset_status = utilities.execute_command(reset_command)
        reset_successful = reset_status == 0
        os.chdir(cur_dir)
    else:
        reset_successful = use_diff_patch(src_path, patch_file, True, is_unified)
        if not reset_successful:
            is_unified = False
            reset_successful = use_diff_patch(src_path, patch_file, True, is_unified)
    return reset_successful, is_unified


def compile_patch(proj_path):
    cur_dir = os.getcwd()
    if values.CONF_CONFIG_SCRIPT and not values.HAS_CONFIGURED:
        os.chdir(values.CONF_SOURCE_DIR)
        script_command = "bash " + values.CONF_CONFIG_SCRIPT
        config_status = utilities.execute_command(script_command)
        # values.HAS_CONFIGURED = config_status == 0

    if values.CONF_BUILD_SCRIPT:
        os.chdir(values.CONF_SOURCE_DIR)
        script_command = "bash " + values.CONF_BUILD_SCRIPT
        compile_status = utilities.execute_command(script_command)
    else:
        proj_path = os.path.dirname(proj_path)
        compile_command = "cd " + proj_path + ";"
        compile_command += "make"
        compile_status = utilities.execute_command(compile_command)
    is_valid = compile_status == 0
    os.chdir(cur_dir)
    return is_valid


def validate_patch(
    patch_id, src_file, patch_file, binary_path, test_oracle, test_id_list
):
    is_compiling = False
    fixed_failed = False
    is_plausible = False
    is_correct = False
    is_high_quality = False
    is_unified = True

    has_patched, is_unified = apply_patch(src_file, patch_file, is_unified=is_unified)
    if has_patched:
        is_compiling = compile_patch(binary_path)
        if is_compiling:
            fixed_failed = tester.run_test_oracle(test_oracle, test_id_list, patch_file)
            if fixed_failed:
                is_plausible = tester.run_test_script(
                    values.CONF_PUB_TEST_SCRIPT, patch_file
                )
                if is_plausible:
                    is_correct = tester.run_test_script(
                        values.CONF_PVT_TEST_SCRIPT, patch_file
                    )
                    if is_correct:
                        is_high_quality = tester.run_test_script(
                            values.CONF_ADV_TEST_SCRIPT, patch_file
                        )
    reset_patch(src_file, patch_file, is_unified=is_unified)
    emitter.highlight(f"\t\t\t\tapplied:{has_patched}")
    emitter.highlight(f"\t\t\t\tcompiled:{is_compiling}")
    emitter.highlight(f"\t\t\t\tfixed-failed:{fixed_failed}")
    emitter.highlight(f"\t\t\t\tplausible:{is_plausible}")
    emitter.highlight(f"\t\t\t\tcorrect:{is_correct}")
    emitter.highlight(f"\t\t\t\thigh-quality:{is_high_quality}")
    return (
        patch_id,
        has_patched,
        is_compiling,
        fixed_failed,
        is_plausible,
        is_correct,
        is_high_quality,
    )
