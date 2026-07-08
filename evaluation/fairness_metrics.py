import math
import numpy as np
import util
from evaluation import decompose_col_val
from evaluation.decompose_col_val import decompose_srt_to_df


def compute_bias(clusters, dataset):
    k = len(clusters)
    R = {}

    #start the groups
    for i in range(0, util.number_of_groups(dataset)):
        R[i] = 0
    for pair in clusters:
        R[pair[3]] = R[pair[3]] + 1
        # if (pair[3] in R.keys()):
        #     R[pair[3]] = R[pair[3]] + 1
        # else:
        #     R[pair[3]] = 1

    values = list(R.values())
    print(values)

    #compute the max difference between the groups
    max_unfairness = (max(values)/k) - (min(values)/k)

    return max_unfairness

def compute_tp_fn_by_group_top_k(clusters, labed_file, dataset, ranking_mode):
    tp = 0
    fn = 0
    tp_fn = {}
    max_recall_per_group = {}
    goldstandard = [line for line in labed_file if line[len(line)-1] == '1']

    print(len(clusters))
    #compute tps
    for pair in clusters:
        for result in labed_file:
            if(pair[0].strip() == result.split('\t')[0].split('VAL')[1].split('COL')[0].strip() and pair[1].strip() == result.split('\t')[1].split('VAL')[1].split('COL')[0].strip()):
                if(result[len(result)-1] == '1'):
                    if (pair[3] in tp_fn.keys()):
                        tp_fn[pair[3]][0] = tp_fn[pair[3]][0] + 1
                    else:
                        tp_fn[pair[3]] = [1, 0]
                    break #do not need to continue

    #compute the max recall in each group
    for pair in goldstandard:
        pair_df = decompose_srt_to_df(pair)
        group = util.pair_is_protected_by_group(pair_df, dataset, False) if ranking_mode == 'm-fair' or ranking_mode == 'none' \
            else util.pair_is_protected(pair_df, dataset, False)
        if (group in max_recall_per_group.keys()):
            max_recall_per_group[group] = max_recall_per_group[group] + 1
        else:
            max_recall_per_group[group] = 1

    discrepancy_between_groups = len(clusters)%len(tp_fn) # compute if the top-k will generate discrepancy between groups. e.g., top-10 with 4 groups will generate 2 groups with +1 pair each
    max_recall_top_k = math.trunc(len(clusters)/len(tp_fn)) #since there is top-k values, the max recall is divided by groups

    for key in tp_fn.keys():
        if key in range(1,discrepancy_between_groups+1): #this groups will benefit by the discrepancy, with one more pair
            fn = min(max_recall_top_k+1, max_recall_per_group[key]) - tp_fn[key][0]
        else:
            fn = min(max_recall_top_k, max_recall_per_group[key]) - tp_fn[key][0]

        if fn < 0: #normalize to avoid negative values for unbalanced groups
            fn = 0
        tp_fn[key][1] = fn

    print(tp_fn)
    return tp_fn

#In top-k approaches (i.e., the max recall possible for the top-k), we assume the true canditates (goldstandard) as the max between the size of the goldstandard and the k value
def compute_TPRP_top_k(clusters, labed_file, dataset, ranking_mode):
    k = len(clusters)
    tp_fn_per_group = compute_tp_fn_by_group_top_k(clusters, labed_file, dataset, ranking_mode)
    for key in tp_fn_per_group.keys():
        tp, fn = tp_fn_per_group.get(key)
        tpr = tp/(tp+fn)
        tp_fn_per_group[key] = tpr
    print(tp_fn_per_group)

    values = list(tp_fn_per_group.values())

    print(values)
    mean_value = np.mean(values)

    #compute the max difference between the groups
    tprp = 1.0 - mean_value

    return tprp


def compute_tp_fp_by_group(clusters, goldstandard):
    tp = 0
    fp = 0
    tp_fp = {}

    print(len(clusters))

    for pair in clusters:
        for result in goldstandard:
            if(pair[0].strip() == result.split('\t')[0].split('VAL')[1].split('COL')[0].strip() and pair[1].strip() == result.split('\t')[1].split('VAL')[1].split('COL')[0].strip()):
                if(result[len(result)-1] == '1'):
                    if (pair[3] in tp_fp.keys()):
                        tp_fp[pair[3]][0] = tp_fp[pair[3]][0] + 1
                    else:
                        tp_fp[pair[3]] = [1, 0]
                    break #do not need to continue
                else:
                    if (pair[3] in tp_fp.keys()):
                        tp_fp[pair[3]][1] = tp_fp[pair[3]][1] + 1
                    else:
                        tp_fp[pair[3]] = [0, 1]
                    break #do not need to continue
                # print(result)

    print(tp_fp)
    return tp_fp


def compute_PPVP(clusters, goldstandard):
    k = len(clusters)
    tp_fp_per_group = compute_tp_fp_by_group(clusters, goldstandard)
    for key in tp_fp_per_group.keys():
        tp, fp = tp_fp_per_group.get(key)
        ppv = tp/(tp+fp)
        tp_fp_per_group[key] = ppv
    print(tp_fp_per_group)

    values = list(tp_fp_per_group.values())
    mean_value = np.mean(values)

    #compute the max difference between the groups and the ideal value (i.e., 1)
    ppvp = 1.0 - mean_value

    return ppvp




# def compute_tp_fn_by_group(clusters, goldstandard, dataset, ranking_mode):
#     tp = 0
#     fn = 0
#     tp_fn = {}
#     visited = []
#
#     print(len(clusters))
#
#     for result in goldstandard:
#         for pair in clusters:
#             if pair[0] == result.split('\t')[0].split('VAL')[1].split('COL')[0] and pair[1] == result.split('\t')[1].split('VAL')[1].split('COL')[0] and pair not in visited:
#                 if result[len(result) - 1] == '1':
#                     if (pair[3] in tp_fn.keys()):
#                         tp_fn[pair[3]][0] = tp_fn[pair[3]][0] + 1
#                     else:
#                         tp_fn[pair[3]] = [1, 0]
#                     visited.append(pair)
#                     break #do not need to continue
#         #the true condition was not found
#         if(result[len(result)-1] == '1'):
#             group = util.pair_is_protected_by_group(decompose_col_val.decompose_srt_to_df(result), dataset, False) \
#                 if ranking_mode == 'm-fair' else util.pair_is_protected(decompose_col_val.decompose_srt_to_df(result), dataset, False)#util.pair_is_protected_by_group(result, dataset, False)
#             if (group in tp_fn.keys()):
#                 tp_fn[group][1] = tp_fn[group][1] + 1
#             else:
#                 tp_fn[pair[3]] = [0, 1]
#
#     print(tp_fn)
#     return tp_fn

# def compute_TPRP(clusters, goldstandard, dataset, ranking_mode):
#     k = len(clusters)
#     tp_fn_per_group = compute_tp_fn_by_group(clusters, goldstandard, dataset, ranking_mode)
#     for key in tp_fn_per_group.keys():
#         tp, fn = tp_fn_per_group.get(key)
#         tpr = tp/(tp+fn)
#         tp_fn_per_group[key] = tpr
#     print(tp_fn_per_group)
#
#     values = list(tp_fn_per_group.values())
#
#     print(values)
#
#     #compute the max difference between the groups
#     tprp = max(values) - min(values)
#
#     return tprp