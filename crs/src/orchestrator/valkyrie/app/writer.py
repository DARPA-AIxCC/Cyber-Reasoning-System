#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import pickle
import json
import os
import shutil
from app import definitions


def write_as_json(data, output_file_path):
    content = json.dumps(data)
    with open(output_file_path, "w") as out_file:
        out_file.writelines(content)


def write_as_pickle(data, output_file_path):
    with open(output_file_path, "wb") as out_file:
        pickle.dump(data, out_file)


def write_filtered_patches(valid_list, patch_dir, output_dir):
    if valid_list:
        for patch_id in valid_list:
            original_file = patch_dir + "/" + str(patch_id) + ".patch"
            sym_link_path = output_dir + "/" + str(patch_id) + ".patch"
            os.system("ln -sf {0} {1}".format(original_file, sym_link_path))
            # shutil.copy(patch_dir + "/" + str(patch_id) + ".patch", output_dir)


def write_ranked_patches(valid_list, patch_dir, output_dir):
    if valid_list:
        for patch_info in valid_list:
            patch_id, t_distance, c_distance, p_edit = patch_info
            rank = "{0:5f}_{1}_{2}".format(t_distance, c_distance, p_edit)
            output_id = "{}_{}".format(rank, patch_id)
            original_file = patch_dir + "/" + str(patch_id) + ".patch"
            sym_link_path = output_dir + "/{}.patch".format(output_id)
            os.system("ln -sf {0} {1}".format(original_file, sym_link_path))
            # shutil.copy(patch_dir + "/" + str(patch_id) + ".patch", output_dir + "/{}.patch".format(output_id))


def write_invalid_patch_list(sorted_reject_list, output_log_path):
    possible_issues = []
    if sorted_reject_list:
        with open(output_log_path, "w") as invalid_log:
            invalid_log.seek(0)
            for patch_id in sorted_reject_list:
                error = ""
                err_file = definitions.DIRECTORY_OUTPUT + "/p{0}.err".format(patch_id)
                if not os.path.isfile(err_file):
                    continue
                with open(err_file, "r", encoding="iso-8859-1") as err_log:
                    error = "".join(err_log.readlines())
                if "syntax error" in error:
                    possible_issues.append(str(patch_id))
                elif "Undefined command" in error:
                    possible_issues.append(str(patch_id))
                elif "has unknown return type" in error:
                    possible_issues.append(str(patch_id))
                invalid_log.write(str(patch_id) + "\n")
                invalid_log.writelines(error)
            invalid_log.truncate()
    return possible_issues


def write_patch_score(score_list, output_log_path):
    if score_list:
        with open(output_log_path, "w") as score_log:
            for item in score_list:
                patch_id, trace_distance, coverage_distance, edit_distance = item
                score_log.write(
                    str(patch_id)
                    + " "
                    + str(trace_distance)
                    + " "
                    + str(coverage_distance)
                    + " "
                    + str(edit_distance)
                    + "\n"
                )
            score_log.close()
