import os
import random
from Levenshtein import distance as edit_distance
import numpy as np
import sys

def read_bin_file(file_name, file_dir):
    # TODO: change to absolute path
    with open(os.path.join(file_dir, file_name), 'rb') as f:
        return f.read()

def distance_wrapper(distance_func,bin_file1, bin_file2):
    return distance_func(bin_file1, bin_file2)

def naive_edit_distance(bin_file1, bin_file2):
    return edit_distance(bin_file1, bin_file2)

def normalised_edit_distance(bin_file1, bin_file2):
    #raw = edit_distance(bin_file1, bin_file2)
    len_max = max(len(bin_file1), len(bin_file2))
    return edit_distance(bin_file1, bin_file2) / len_max

def syntactic_based_distance(bin_file1, bin_file2):
    pass

# select the test cases that are most different from the selected test cases
def distance_calculation(selected_ls,select_dir, generated_ls, gen_dir):
    distance = np.zeros((len(selected_ls), len(generated_ls)))
    # construct distance matrix
    for i in range(len(selected_ls)):
        for j in range(i+1, len(generated_ls)):
            distance[i][j] = distance_wrapper(
                naive_edit_distance,
                 read_bin_file(selected_ls[i],select_dir), 
                 read_bin_file(generated_ls[j],gen_dir))
    
    # select the most far away
    sums = np.sum(distance, axis=0)  # sum along columns
    column_with_max_sum = np.argmax(sums)  # find index of column with max sum
    use_seed = generated_ls[column_with_max_sum]
    return use_seed

def main(temp_dir, output_dir):
    # if out_dir is empty
    if len(os.listdir(output_dir)) == 0:
        # randomly select 5 test cases
        init = random.sample( os.listdir(temp_dir),5)
        # copy all files in init to output_dir
        for file in init:
            os.system("cp " + os.path.join(temp_dir, file) + " " + os.path.join(output_dir, file))
    else:
        init = os.listdir(output_dir)
    file_selected = distance_calculation(os.listdir(output_dir), output_dir ,os.listdir(temp_dir), temp_dir)
    print("selected files: " + file_selected)
    os.system("cp " + os.path.join(temp_dir, file_selected) + " " + os.path.join(output_dir, file_selected))
#        selected_batch = copy.deepcopy(init)


def entry_point():
    # process three arguments
    if len(sys.argv) != 3:
        print("Usage: adaptive_test_online_entry.py temp_dir output_dir")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    entry_point()
