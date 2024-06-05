import os
from app import utilities, definitions, debugger, tester, emitter


def rewrite_patch(patch_expr, instr_address, binary_path):
    patch_expr = patch_expr.strip().replace(";", "")
    patched_binary_path = "{0}.patched".format(binary_path)
    rewrite_command = "cd " + definitions.DIRECTORY_LIB + ";"
    rewrite_command += (
        "e9tool -M 'addr==0x{0}' -P "
        "'entry(\"{1}\", base, static addr, state)@patch_hook' {2}"
        " -E .plt -o {3}".format(
            instr_address, patch_expr, binary_path, patched_binary_path
        )
    )
    utilities.execute_command(rewrite_command)
    return patched_binary_path


def validate_patch(patch_id, fragment, binary_path, test_oracle, test_id_list):
    break_point, jump_point, patch_content = fragment
    patch_expr = patch_content[0]
    inst_address = debugger.get_instruction_address(binary_path, break_point)
    patched_binary = rewrite_patch(patch_expr, inst_address, binary_path)
    is_valid = tester.test_patched_binary(patched_binary, test_oracle, test_id_list)
    return patch_id, is_valid


def enable_tracing(binary_path):
    instrumented_binary_path = "{0}.inst_trace".format(binary_path)
    e9plugin_dir = definitions.DIR_MAIN + "/e9plugins"
    e9command = "cd {}; e9tool -s -M 'asm=/j.*/' -P 'entry()@trace' {} -o {}".format(
        e9plugin_dir, binary_path, instrumented_binary_path
    )
    utilities.execute_command(e9command)
    return instrumented_binary_path


def enable_coverage(binary_path):
    if not binary_path:
        return None
    instrumented_binary_path = "{0}.inst_coverage".format(binary_path)
    e9command = "e9afl {} -o {}".format(binary_path, instrumented_binary_path)
    utilities.execute_command(e9command)
    return instrumented_binary_path
