import json
import pickle
import os
from app import utilities, values


def read_json(file_path):
    json_data = None
    if os.path.isfile(file_path):
        with open(file_path, "r") as in_file:
            content = in_file.readline()
            json_data = json.loads(content)
    return json_data


def read_pickle(file_path):
    pickle_object = None
    if os.path.isfile(file_path):
        with open(file_path, "rb") as pickle_file:
            pickle_object = pickle.load(pickle_file)
    return pickle_object


def read_patch(file_path):
    added_lines = dict()
    removed_lines = dict()
    require_compile = False
    jump_loc = None
    if os.path.isfile(file_path):
        with open(file_path, "r") as in_file:
            line_offset = 0
            content = in_file.readlines()
            patch_loc = None
            patch_expr = None
            inserts = []
            deletes = []
            if values.CONF_SOURCE_FILE:
                source_file = values.CONF_SOURCE_FILE
            elif values.CONF_SOURCE_DIR:
                source_file = content[0].split(" ")[1].split("\t")[0].replace("\n", "")
            else:
                source_file = content[0].split(" ")[1].split("\t")[0].replace("\n", "")
                source_file = source_file.replace("a/src/", "").replace("b/src/", "")
                source_file = source_file.split("/")[-1].replace("_bk", "")

            for line in content[2:]:
                if line[0] == "@":
                    patch_line_number = int(
                        line.split(" ")[1]
                        .replace("\n", "")
                        .split(",")[0]
                        .replace("+", "")
                        .replace("-", "")
                    )

                    if patch_loc:
                        if inserts or deletes:
                            added_lines[patch_loc] = inserts
                            removed_lines[patch_loc] = deletes
                        inserts = []
                        deletes = []
                    patch_loc = source_file + ":" + str(patch_line_number)
                elif line[0] == "+":
                    if "#include" in line:
                        require_compile = True
                        return source_file, dict(), dict(), require_compile, jump_loc
                    if len(line.replace("\n", "").split(";")) == 1:
                        inserts.append(line.replace("\n", "")[1:])
                    else:
                        if any(x in line for x in ["for", "for("]):
                            inserts.append(line.replace("\n", "")[1:])
                        elif any(x in line for x in ["if", "if("]):
                            open_pos = line.find("(")
                            n_open = 0
                            n_close = 0
                            close_pos = open_pos
                            for x in line[open_pos:]:
                                close_pos += 1
                                if x == "(":
                                    n_open += 1
                                elif x == ")":
                                    n_close += 1
                                if n_open == n_close:
                                    break
                            if_condition = line[:close_pos]
                            rest_line = line[close_pos:]
                            inserts.append(if_condition.replace("\n", "")[1:])
                            inserts.append(rest_line.replace("\n", ""))
                        else:
                            sep_lines = line[1:].replace("\n", "").split(";")
                            for l in sep_lines:
                                if len(l) > 1:
                                    inserts.append(l)
                elif line[0] == "-":
                    deletes.append(line.replace("\n", "")[1:])
                    if "/* jump:" in line:
                        jump_line = line.split("jump:")[1].split(" ")[0]
                        jump_loc = source_file + ":" + str(jump_line)
                elif len(line) == 0:
                    continue
            if inserts or deletes:
                added_lines[patch_loc] = inserts
                removed_lines[patch_loc] = deletes
    return source_file, added_lines, removed_lines, require_compile, jump_loc
