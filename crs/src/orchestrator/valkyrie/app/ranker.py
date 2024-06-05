import os.path
import operator
from app import distance, writer, definitions, parallel, emitter


def collect_trace(patch_list, test_id_list, test_oracle, binary_path):
    emitter.sub_sub_title("Collecting Traces")
    emitter.normal("\t\tevaluating patches")
    trace_info = parallel.trace_patch_list_gdb(
        patch_list, test_oracle, test_id_list, binary_path
    )
    return trace_info


def collect_coverage(patch_list, test_id_list, test_oracle, binary_path):
    emitter.sub_sub_title("Collecting Coverage Info")
    emitter.normal("\t\tevaluating patches")
    coverage_info = parallel.coverage_patch_list_gdb(
        patch_list, test_oracle, test_id_list, binary_path
    )
    return coverage_info


def rank_patches(patch_list, test_id_list, test_oracle, binary_path):
    coverage_info = collect_coverage(patch_list, test_id_list, test_oracle, binary_path)
    # trace_info = collect_trace(patch_list, test_id_list, test_oracle, binary_path)
    trace_info = dict()
    edit_distance_info = distance.edit_distance(patch_list)
    emitter.sub_sub_title("Ranking Patches")
    emitter.normal("\t\tcomputing distance score")
    score_vec_list = parallel.compute_patch_vectors(
        patch_list, coverage_info, trace_info, edit_distance_info
    )
    ranked_list = sorted(score_vec_list, key=operator.itemgetter(1, 2, 3))
    writer.write_patch_score(ranked_list, definitions.FILE_PATCH_SCORE)
    return ranked_list
