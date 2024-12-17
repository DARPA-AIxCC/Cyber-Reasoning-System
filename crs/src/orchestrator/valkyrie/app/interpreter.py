import os
import re


def has_function_call(statement):
    if any(
        x in statement
        for x in [
            "return ",
            "while ",
            "if ",
            "for ",
            "while(",
            "if(",
            "for(",
            "switch(",
        ]
    ):
        return False
    # pattern = r"[A-Za-z0-9_]+\([A-Za-z0-9(\()*]+\)"
    pattern = r"[A-Za-z0-9_ ]*\("
    return re.match(pattern, statement)


def convert_assignment_statement(patch_line):
    gdb_command = ""
    # check if assignment is in declaration
    lhs_str = patch_line.split("=")[0].strip().split(" ")[-1]
    rhs_str = patch_line.split("=", 1)[1].replace(";", "")
    if any(x in patch_line for x in ["+=", "++", "--", "-=", "/=", "*="]):
        gdb_command += "call " + patch_line.replace(";", "") + "\n"
    elif "=" in patch_line.replace("==", "").replace("!=", "").replace(
        ">=", ""
    ).replace("<=", ""):
        gdb_command += f"set var {lhs_str}={rhs_str}\n"

    return gdb_command


def convert_function_call(patch_line):
    gdb_command = "call (void)" + patch_line.replace(";", "") + "\n"
    return gdb_command


def convert_if_condition(break_point, jump_point, patch_line):
    gdb_command = ""
    if_condition = None
    rest_line = None
    patch_line = patch_line[patch_line.find("if") :]
    source_file, source_line = break_point.split(":")
    step_point = source_file + ":" + str(int(source_line) + 1)
    if step_point == jump_point:
        open_pos = patch_line.find("(")
        n_open = 0
        n_close = 0
        close_pos = open_pos
        for x in patch_line[open_pos:]:
            close_pos += 1
            if x == "(":
                n_open += 1
            elif x == ")":
                n_close += 1
            if n_open == n_close:
                break
        if_condition = patch_line[open_pos:close_pos]
        rest_line = patch_line[close_pos:]
    else:
        if_condition = patch_line.replace("if ", "").replace("{", "")
    gdb_command += "if {}\n".format(if_condition)

    if step_point == jump_point:
        if rest_line:
            if has_function_call(rest_line):
                gdb_command += convert_function_call(rest_line)
            else:
                gdb_command += "call {}\n".format(rest_line)
    gdb_command += "jump {}\n".format(step_point)
    gdb_command += "else\n"
    gdb_command += "jump {}\n".format(jump_point)
    gdb_command += "end \n"
    return gdb_command


def convert_for_loop(break_point, jump_point, patch_line):
    gdb_command = ""
    patch_line = patch_line[patch_line.find("for") :]
    tokens = patch_line.replace("for", "").replace("{", "").split(";")
    # initialization
    gdb_command += "if $valkyrie_init \n"
    initialize_line = tokens[0]
    initialize_line = initialize_line[initialize_line.find("(") + 1 :].strip()
    if initialize_line:
        for initializers in initialize_line.split(","):
            gdb_command += "set var {}\n".format(
                initializers.replace("int", "").replace("short", "")
            )
    gdb_command += "set $valkyrie_init = 0\n"
    gdb_command += "end \n"

    source_file, start_line = break_point.split(":")
    source_file, end_line = jump_point.split(":")
    step_point = source_file + ":" + str(int(start_line) + 1)
    end_point = source_file + ":" + str(int(end_line) - 1)
    condition = tokens[1].strip()

    # condition-check
    if not condition:
        condition = "1"
    gdb_command += "if ({})\n".format(condition)
    gdb_command += "jump {}\n".format(step_point)
    gdb_command += "else\n"
    gdb_command += "jump {}\n".format(jump_point)
    gdb_command += "end\n"
    gdb_command += "end\n"

    # post-iteration
    gdb_command += "break {}\n".format(end_point)
    gdb_command += "commands\n"
    gdb_command += "silent\n"
    increment_line = tokens[2]
    increment_line = increment_line[: increment_line.rfind(")")]
    if increment_line:
        gdb_command += "set var {}\n".format(increment_line)
    gdb_command += "if ({})\n".format(condition)
    gdb_command += "jump {}\n".format(step_point)
    gdb_command += "else\n"
    gdb_command += "jump {}\n".format(jump_point)
    gdb_command += "end\n"

    return gdb_command


def convert_while_loop(break_point, jump_point, patch_line):
    gdb_command = ""
    patch_line = patch_line[patch_line.find("while") :]
    source_file, start_line = break_point.split(":")
    source_file, end_line = jump_point.split(":")
    step_point = source_file + ":" + str(int(start_line) + 1)
    end_point = source_file + ":" + str(int(end_line) - 1)
    condition = patch_line.replace("while", "").replace("{", "").strip()[1:-1]
    gdb_command += "if {}\n".format(condition)
    gdb_command += "jump {}\n".format(step_point)
    gdb_command += "else\n"
    gdb_command += "jump {}\n".format(jump_point)
    gdb_command += "end\n"
    gdb_command += "end\n"
    gdb_command += "break {}\n".format(end_point)
    gdb_command += "commands\n"
    gdb_command += "silent\n"
    gdb_command += "if {}\n".format(condition)
    gdb_command += "jump {}\n".format(step_point)
    gdb_command += "else\n"
    gdb_command += "jump {}\n".format(jump_point)
    gdb_command += "end\n"
    return gdb_command


def convert_to_gdb_command(patch_fragment, break_point, jump_point, snapshot_file):
    gdb_command = ""
    is_iteration = False
    gdb_command += "break {}\n".format(break_point)
    gdb_command += "commands\n"
    gdb_command += "silent\n"
    if snapshot_file:
        gdb_command += "generate-core-file {}\n".format(snapshot_file)
    for patch_line in patch_fragment:
        patch_line = patch_line.replace("\t", "").strip()
        comments = re.search("/\*([^*]|[\r\n])*\*/", patch_line)
        if comments:
            patch_line = patch_line.replace(comments[0], "")

        if "//prophet" in patch_line:
            continue

        if "return " in patch_line:
            gdb_command += patch_line + "\ncontinue\n"
        elif "if (" in patch_line:
            gdb_command += convert_if_condition(break_point, jump_point, patch_line)
            jump_point = None
        elif "while (" in patch_line:
            is_iteration = True
            gdb_command += convert_while_loop(break_point, jump_point, patch_line)
            jump_point = None
        elif "for (" in patch_line:
            is_iteration = True
            gdb_command += convert_for_loop(break_point, jump_point, patch_line)
            jump_point = None
        elif (
            "for (" not in patch_line
            and "while (" not in patch_line
            and "if (" not in patch_line
        ):
            if "=" in patch_line.replace("==", "").replace("!=", "").replace(
                ">=", ""
            ).replace("<=", ""):
                # gdb_command += "set var {}\n".format(patch_line.replace(";", ""))
                gdb_command += convert_assignment_statement(patch_line)
            elif any(x in patch_line for x in ["+=", "++", "--", "-=", "/=", "*="]):
                gdb_command += "call " + patch_line.replace(";", "") + "\n"
        elif has_function_call(patch_line):
            gdb_command += convert_function_call(patch_line)
        else:
            patch_line = patch_line.replace("}", "").replace("{", "")
            if has_function_call(patch_line):
                gdb_command += "call "
            gdb_command += patch_line.replace(";", "") + "\n"

    if jump_point and not is_iteration:
        gdb_command += "jump {}\n".format(jump_point)
    if is_iteration:
        gdb_command = "set var $valkyrie_init = 1\n" + gdb_command
    return gdb_command, is_iteration
