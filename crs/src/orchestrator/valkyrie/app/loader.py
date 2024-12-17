import pathlib
import json
import subprocess
import os
import shutil
import traceback
import signal
import time
from app import (
    emitter,
    logger,
    definitions,
    values,
    e9patch,
    configuration,
    reader,
    debugger,
    tester,
    utilities,
    gdb,
    compiler,
)
from os.path import dirname, abspath
from os import listdir
from os.path import isfile, join


def load_patch_file(patch_file):
    fragment_list = []
    patch_index = patch_file.split("/")[-1]
    if os.path.getsize(patch_file) == 0:
        return None
    is_unhandled = False
    src_file, added_lines, removed_lines, req_compile, jump_point = reader.read_patch(
        patch_file
    )
    break_point_list = list(
        set((list(added_lines.keys()) + list(removed_lines.keys())))
    )
    for break_point in break_point_list:
        src_path, line_number = break_point.split(":")
        patch_content = None
        if not jump_point:
            if break_point in removed_lines.keys():
                jump_point = (
                    src_path
                    + ":"
                    + str(int(line_number) + len(removed_lines[break_point]))
                )
        if break_point in added_lines.keys():
            patch_content = added_lines[break_point]
        fragment_list.append((break_point, jump_point, patch_content))
    if not req_compile and not added_lines and not removed_lines:
        is_unhandled = True
    return patch_index, fragment_list, src_file, patch_file, req_compile, is_unhandled


def load_patch_list(dir_patch):
    emitter.sub_sub_title("Loading Patches")
    patch_list = dict()
    unhandled_list = []
    empty_list = []
    if os.path.isdir(dir_patch):
        regex = "*"
        file_list = sorted(
            [str(x) for x in pathlib.Path(dir_patch).rglob(regex) if os.path.isfile(x)]
        )
        # file_list = [os.path.join(dir_patch, t) for t in list_files]
        # file_list = sorted([join(dir_patch, f) for f in listdir(dir_patch, ) if isfile(join(dir_patch, f)) and ".patch" in f],
        #                    key=lambda x: int(x.split("_")[1].replace(".patch", "")))
        if not file_list:
            emitter.error("\t\t[error] patch dir does not contain any patch")
        count_patch = 0
        emitter.normal("\t\t reading patches")
        patches_per_tool = dict()
        for patch_file in file_list[: values.DEFAULT_LIMIT]:
            count_patch = count_patch + 1
            fragment_list = []
            patch_dir = os.path.dirname(patch_file)
            patch_dir_rel = str(patch_dir).replace(values.CONF_PATCH_DIR + "/", "")
            patch_index = patch_file.split("/")[-1]

            if patch_dir_rel:
                patch_index = f"{patch_dir_rel}:{patch_index}"
                if patch_dir_rel not in patches_per_tool:
                    patches_per_tool[patch_dir_rel] = list()
                patches_per_tool[patch_dir_rel].append(patch_index)

            if len(patches_per_tool[patch_dir_rel]) > values.DEFAULT_LIMIT_PER_DIR:
                continue
            if os.path.getsize(patch_file) == 0:
                empty_list.append(patch_index)
                continue
            try:
                src_file, added_lines, removed_lines, req_compile, jump_point = reader.read_patch(patch_file)
            except Exception as e:
                emitter.warning(f"could not read patch file {patch_file}")
                continue

            break_point_list = list(
                set((list(added_lines.keys()) + list(removed_lines.keys())))
            )
            if values.DEFAULT_PATCH_MODE == definitions.VALUE_OPERATE_MODE_COMPILE:
                patch_list[patch_index] = (
                    fragment_list,
                    src_file,
                    patch_file,
                    req_compile,
                )
            else:
                for break_point in break_point_list:
                    src_path, line_number = break_point.split(":")
                    patch_content = None
                    if jump_point is None:
                        if break_point in removed_lines.keys():
                            jump_point = (
                                src_path
                                + ":"
                                + str(
                                    int(line_number) + len(removed_lines[break_point])
                                )
                            )
                    if break_point in added_lines.keys():
                        patch_content = added_lines[break_point]
                    fragment_list.append((break_point, jump_point, patch_content))
                if not req_compile and not added_lines and not removed_lines:
                    unhandled_list.append(patch_index)
                else:
                    patch_list[patch_index] = (
                        fragment_list,
                        src_file,
                        patch_file,
                        req_compile,
                    )
        emitter.normal("\t\t found {0} number of patches".format(len(patch_list)))
    else:
        emitter.error("\t\t[error] patch dir does not exist")
    if unhandled_list:
        # sorted_list = sorted([int(x) for x in unhandled_list])
        # print("Unhandled List")
        # print("Count: " + str(len(unhandled_list)))
        # print(sorted_list)
        values.COUNT_UNHANDLED = len(unhandled_list)
    if empty_list:
        values.COUNT_EMPTY = len(empty_list)
    return patch_list
