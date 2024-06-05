import os
from app import reader


import sys

# Christopher P. Matthews
# christophermatthews1985@gmail.com
# Sacramento, CA, USA


def levenshtein_distance(s, t):
    """ From Wikipedia article; Iterative with two matrix rows. """
    if s == t:
        return 0
    elif len(s) == 0:
        return len(t)
    elif len(t) == 0:
        return len(s)
    v0 = [None] * (len(t) + 1)
    v1 = [None] * (len(t) + 1)
    for i in range(len(v0)):
        v0[i] = i
    for i in range(len(s)):
        v1[0] = i + 1
        for j in range(len(t)):
            cost = 0 if s[i] == t[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        for j in range(len(v0)):
            v0[j] = v1[j]

    return v1[len(t)]


# Dynamic Programming implementation of LCS problem
# This code is contributed by Nikhil Kumar Singh(nickzuck_007)
# Source: https://www.geeksforgeeks.org/longest-common-subsequence-dp-4


def lcs(X, Y):
    # find the length of the strings
    m = len(X)
    n = len(Y)

    # declaring the array for storing the dp values
    L = [[0] * (n + 1) for i in range(m + 1)]

    """Following steps build L[m + 1][n + 1] in bottom up fashion
    Note: L[i][j] contains length of LCS of X[0..i-1]
    and Y[0..j-1]"""
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 or j == 0:
                L[i][j] = 0
            elif X[i - 1] == Y[j - 1]:
                L[i][j] = L[i - 1][j - 1] + 1
            else:
                L[i][j] = max(L[i - 1][j], L[i][j - 1])

    # L[m][n] contains the length of LCS of X[0..n-1] & Y[0..m-1]
    return L[m][n]


def edit_distance(patch_list):
    edit_distance_info = dict()
    for patch_id in patch_list:
        patch_info = patch_list[patch_id]
        _, _, patch_file, _, _ = patch_list[patch_id]
        patch_file = patch_file.replace("patch-valid", "patches")
        _, added_lines, removed_lines, _, _ = reader.read_patch(patch_file)
        original_text = ""
        updated_text = ""
        for loc in added_lines:
            updated_text += "".join(added_lines[loc])
        for loc in removed_lines:
            original_text += "".join(removed_lines[loc])
        original_text = original_text.strip().replace("\t", "").replace("\n", "")
        updated_text = updated_text.strip().replace("\t", "").replace("\n", "")
        edit_distance = levenshtein_distance(original_text, updated_text)
        edit_distance_info[patch_id] = edit_distance
    return edit_distance_info


def trace_distance(patched_list, original_list):
    distance_info = dict()
    for t_id in patched_list:
        orig_trace = original_list[t_id]
        patched_trace = patched_list[t_id]
        lcs_distance = lcs(orig_trace, patched_trace)
        distance = 1 - (lcs_distance / max(len(patched_trace), len(orig_trace)))
        distance_info[t_id] = distance
    return distance_info


def coverage_distance(patched_list, original_list):
    distance_info = dict()
    for t_id in patched_list:
        distance = 0
        orig_coverage = original_list[t_id]
        patched_coverage = patched_list[t_id]
        edges = list(set(list(orig_coverage.keys()) + list(patched_coverage.keys())))
        for edge in edges:
            if edge in patched_coverage.keys():
                if edge not in orig_coverage.keys():
                    distance += int(patched_coverage[edge])
                else:
                    distance += abs(
                        int(patched_coverage[edge]) - int(orig_coverage[edge])
                    )
            else:
                distance += int(orig_coverage[edge])
        distance_info[t_id] = distance
    return distance_info


def compute_score_vector(
    patch_id, p_trace, p_coverage, orig_trace, orig_coverage, p_edit
):
    # trace_distance_vector = trace_distance(p_trace, orig_trace)
    coverage_distance_vector = coverage_distance(p_coverage, orig_coverage)
    # t_distance = sum(trace_distance_vector.values()) / len(trace_distance_vector)
    c_distance = sum(coverage_distance_vector.values()) / len(coverage_distance_vector)
    t_distance = 0
    return (patch_id, t_distance, c_distance, p_edit)
