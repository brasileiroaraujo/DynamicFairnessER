import sys
from collections import defaultdict
from pathlib import Path

from lemon import Attribution, MatchingAttributionExplanation

# from data_distribution_assessment import data_assessment_menager

sys.path.insert(2, '../GNEM')
from _dummy_thread import exit

import pandas as pd
import time
from typing import List, Tuple, Dict

import torch
import torch.nn as nn

from EmbedModel import EmbedModel
from GCN import gcn
from streaming.accuracy_evaluator import perform_evaluation
from streaming.controller_fairER_streaming import match_rank_streaming, match_gnem_rank_streaming, \
    match_rank_streaming_explantion
import matcher

import subprocess
import sys
from importlib_metadata import version

import warnings
warnings.filterwarnings("ignore", message="An input tensor was not cuda.", category=UserWarning)
warnings.filterwarnings("ignore", message="The prediction score from explanation a and b", category=UserWarning)



# ct=Consumer({'bootstrap.servers':'localhost:9092','group.id':'python-consumer','auto.offset.reset':'earliest'})
#
# print('Available topics to consume: ', ct.list_topics().topics)
#
# ct.subscribe(['target'])
################

attribute_explanation: Dict[str, Dict[str, float]] = defaultdict(lambda: {"weight_sum": 0.0, "potential_sum": 0.0, "count": 0})

def sortBySimilarity(element):
    return float(element[2])

def sortBySimilarityExplanation(element):
    return float((0.9 * element[2]) + (0.1 * element[4]))
    # return float(element[2])#just to compare with no explanation approach

def sortBySimilarityExplanationPareto(incremental_clusters, top_k):
    """
    Seleciona os top_k pares baseando-se na fronteira de Pareto (similarity x EFS).
    Se a quantidade de pares na fronteira for menor que top_k, preenche com os dominados.

    Parâmetros:
        incremental_clusters (list of tuples):
            Lista no formato (entidade1, entidade2, similarity, group_id, EFS)
        top_k (int): número de pares a retornar.

    Retorna:
        Lista de top_k pares, priorizando os da fronteira de Pareto.
    """
    def is_dominated(p1, p2):
        return (
                (p2[0] >= p1[0] and p2[1] >  p1[1]) or
                (p2[0] >  p1[0] and p2[1] >= p1[1])
        )

    pareto_front = []
    dominated = []
    for i, a in enumerate(incremental_clusters):
        a_obj = (a[2], a[4])  # (similarity, EFS)
        dominated_flag = False
        for j, b in enumerate(incremental_clusters):
            if i == j:
                continue
            b_obj = (b[2], b[4])
            if is_dominated(a_obj, b_obj):
                dominated_flag = True
                break
        if not dominated_flag:
            pareto_front.append(a)
        else:
            dominated.append(a)

    # Ordena fronteira por similarity desc
    pareto_front.sort(key=lambda el: el[2], reverse=True)

    # Ordena dominados por similarity desc
    dominated.sort(key=lambda el: el[2], reverse=True)

    # Junta: primeiro os da fronteira, depois os dominados, até atingir top_k
    result = pareto_front + dominated
    return result[:top_k]



def compute_EFS_average(incremental_clusters):
    sum = 0
    for element in incremental_clusters:
        sum += element[4]
    print("ES: " + str(sum/len(incremental_clusters)))
    return sum/len(incremental_clusters)


def add_explanation_info(clusters, exp):
    clusters_with_explanation = []
    for element in clusters:
        explanation = exp[element[0] + " || " + element[1]]
        exp_score = get_explanation_score(explanation.attributions)
        element = element + (exp_score,)
        clusters_with_explanation.append(element)
    return clusters_with_explanation

def merge_clusters(clusters, incremental_clusters, k_ranking, ranking_mode):
    incremental_clusters.extend(clusters)
    incremental_clusters.sort(key=sortBySimilarity, reverse=True)
    if ranking_mode == 'm-fair':
        print("Running m-fair")
        return run_steraming_ranking_by_groups(incremental_clusters, 1, k_ranking) #1 = the first protected group
    else: #default fair-er ranking
        print("Running fair-er")
        return fairness_ranking(incremental_clusters, True, k_ranking) #True = first the protected group

def merge_clusters_with_explantion(clusters, incremental_clusters, k_ranking, ranking_mode):
    current_keys = {x[0] for x in clusters}

    incremental_clusters.extend(clusters)

    #select the sort methor
    incremental_clusters.sort(key=sortBySimilarity, reverse=True) #only similarity (test when explanation is considered to rank)
    # incremental_clusters.sort(key=sortBySimilarityExplanation, reverse=True) #Weighting: similarity and explanation
    # incremental_clusters = sortBySimilarityExplanationPareto(incremental_clusters, top_k=len(incremental_clusters)) #Pareto frontier: similarity and explanation


    if ranking_mode == 'm-fair':
        print("Running m-fair")
        output = run_steraming_ranking_by_groups(incremental_clusters, 1, k_ranking) #1 = the first protected group
        new_result_keys = {x[0] for x in output}
        print("NEW PAIRS IN RESULT FOR THE CURRENT INCREMENT: " + str(len(current_keys & new_result_keys)))
        return output
    else: #default fair-er ranking
        print("Running fair-er")
        return fairness_ranking(incremental_clusters, True, k_ranking) #True = first the protected group

def add_protected_group(dict_groups, index, tuple):
    if dict_groups.get(index) == None:
        dict_groups[index]=[tuple]
    else:
        dict_groups.get(index).append(tuple)

def run_steraming_ranking_by_groups(candidates, nextGroup, results_limit):
    matched_ids_left = set()
    matched_ids_right = set()
    matches = []

    # nonprotected_candidates = []
    grouped_candidates = {}
    for x in candidates:
        add_protected_group(grouped_candidates, int(x[3]), x) #index 0 is the non-protected group, others are protected

    #groups_indexes works as a interface to determine the netx group to be benefit (selected)
    #it works together nextGroup, which iterate over this list using the index (starting in 0)
    groups_indexes = list(range(0, max(grouped_candidates.keys())+1))

    while (groups_indexes) and (len(matches) < results_limit): #if groups_indexes is empty, means all groups are completely used
        if grouped_candidates.get(groups_indexes[nextGroup]) == None or len(grouped_candidates.get(groups_indexes[nextGroup])) == 0:
            groups_indexes.pop(nextGroup)
            nextGroup = 0 if nextGroup >= len(groups_indexes) else nextGroup
            continue

        cand = grouped_candidates.get(groups_indexes[nextGroup]).pop(0)

        # unique mapping constraint check
        if cand[0] in matched_ids_left or cand[1] in matched_ids_right:
            #print('Skipping candidate: ', cand, 'for violating unique mapping constraint')
            continue

        # add pair to matches
        matches.append(cand)
        matched_ids_left.add(cand[0])
        matched_ids_right.add(cand[1])

        if groups_indexes:#(nextGroup and nonprotected_candidates) or (not nextGroup and protected_candidates):
            nextGroup = 0 if nextGroup == (len(groups_indexes)-1) else nextGroup+1 # swap queues
            #print('swapping to ', 'protected' if nextProtected else 'nonprotected', 'queue')

    return matches

def fairness_ranking(candidates, nextProtected, results_limit):
    matched_ids_left = set()
    matched_ids_right = set()
    matches = []

    protected_candidates = [x for x in candidates if x[3]]
    nonprotected_candidates = [x for x in candidates if not x[3]]

    #print(protected_candidates)
    #print(nonprotected_candidates)

    while (protected_candidates or nonprotected_candidates) and (len(matches) < results_limit):
        cand = protected_candidates.pop(0) if ((nextProtected and protected_candidates) or not nonprotected_candidates) else nonprotected_candidates.pop(0)
        #print(cand)

        # unique mapping constraint check
        if cand[0] in matched_ids_left or cand[1] in matched_ids_right:
            #print('Skipping candidate: ', cand, 'for violating unique mapping constraint')
            continue

        # add pair to matches
        matches.append(cand)
        matched_ids_left.add(cand[0])
        matched_ids_right.add(cand[1])

        if (nextProtected and nonprotected_candidates) or (not nextProtected and protected_candidates):
            nextProtected = not nextProtected  # swap queues
            #print('swapping to ', 'protected' if nextProtected else 'nonprotected', 'queue')

    return matches


def setUpDitto(task, lm="distilbert", use_gpu=True, fp16="store_true",
               checkpoint_path='checkpoints/', dk=None, summarize="store_true", max_len=256, threshold=0):
    #ditto dependency with gnem conflict
    # if version('transformers') != '3.4.0':
    #     subprocess.check_call([sys.executable, "-m", "pip", "install", "transformers==3.4.0"])

    print("---- Configuring Ditto ----")
    # load the models
    matcher.set_seed(123)
    config, model = matcher.load_model(task, checkpoint_path,
                                       lm, use_gpu, fp16)

    summarizer = dk_injector = None
    if summarize:
        summarizer = matcher.Summarizer(config, lm)

    if dk is not None:
        if 'product' in dk:
            dk_injector = matcher.ProductDKInjector(config, dk)
        else:
            dk_injector = matcher.GeneralDKInjector(config, dk)

    # tune threshold
    if (threshold <= 0):
        print("---- Tuning Threshold ----")
        threshold = matcher.tune_threshold_parameterized(config, model, task, summarize, lm, max_len, dk)
    print('APPLIED THRESHOLD: ' + str(threshold))

    print("---- Ditto Configured ----")

    return config, model, threshold, summarizer, dk_injector

def setUpGNEM(data, useful_field_num, gpu=[0], gcn_layer=1):
    #gnem dependency with ditto conflict
    if version('transformers') != '2.8.0':
        subprocess.check_call([sys.executable, "-m", "pip", "install", "transformers==2.8.0"])

    data = (data.replace("-", "_")).lower()
    checkpoint_path = "pretrained/"+data+"_bert.pth"
    embedmodel = EmbedModel(useful_field_num=useful_field_num,device=gpu)

    gcn_dim = 768
    model = gcn(dims=[gcn_dim]*(gcn_layer + 1))

    criterion = nn.CrossEntropyLoss().to(embedmodel.device)

    # logger = set_logger()

    if checkpoint_path:
        checkpoint = torch.load(checkpoint_path)
        if len(gpu) == 1:
            new_state_dict = {k.replace('module.', ''): v for k, v in checkpoint["embed_model"].items()}
            embedmodel.load_state_dict(new_state_dict)
        else:
            embedmodel.load_state_dict(checkpoint["embed_model"])
        model.load_state_dict(checkpoint["model"])
        test_type = [checkpoint["type"]]
        # logger.info("Test Type:\t{}".format(checkpoint["type"]))
    # else:
    #     test_type = test_type

    embedmodel = embedmodel.to(embedmodel.device)
    model = model.to(embedmodel.device)

    return model, embedmodel, criterion

def extract_attribute_tuples(attributions: List[Attribution]) -> List[Tuple[str, str, float, float]]:
    # result = []

    for attr in attributions:
        for pos in attr.positions:
            side, field = pos[0], pos[1]
            key = f"{side}.{field}"
            if field != 'id': #remove id column of results
                # result.append((side, field, attr.weight, attr.potential))
                # update global info
                attribute_explanation[key]["weight_sum"] += attr.weight
                attribute_explanation[key]["potential_sum"] += (attr.potential if attr.potential != None else 0)
                attribute_explanation[key]["count"] += 1

    # return result


def explanation_score_local(s: float, p: float, alpha_factor: float = 1) -> float:
    """
    Calcula o Explanation Score (ES) baseado nos parâmetros s e p.

    Fórmula:
        ES = s + p * abs(s) * (1 - abs(s))

    Onde:
        s ∈ [-1, 1]  → score principal
        p ∈ [-1, 1]  → potential (atua como atenuador/potencializador)

    Retorna:
        ES ∈ [-1, 1] aproximadamente
    """
    ES = s + alpha_factor * p * abs(s) * (1 - abs(s))
    # Garante que o valor fique limitado ao intervalo [-1, 1]
    ES = max(min(ES, 1.0), -1.0)
    return ES

def get_explanation_score(attributions: List[Attribution]):
    computed_att = 0
    local_scores = 0
    for attr in attributions:
        if (attr.potential == None):
            local_scores += attr.weight
        else:
            local_scores += explanation_score_local(attr.weight, attr.potential)
        computed_att += 1

    es = local_scores/computed_att
    return es

# def get_explanation_score(attributions: List[Attribution]):
#     max_abs_score = 1e-8 #avoid division by zero
#     es = 0.0
#
#     for attr in attributions:
#         if (attr.weight > 1 or attr.weight < -1 or attr.potential > 1 or attr.potential < -1):
#             print("WEIGHT: " + str(attr.weight))
#             print("POTENTIAL: " + str(attr.potential))
#         max_abs_score = max(max_abs_score, abs(attr.weight))
#
#     for attr in attributions:
#         normalized_score = attr.weight / max_abs_score
#         local_es = normalized_score * (attr.potential if attr.potential != None else 1)
#         if (normalized_score < 0 and attr.potential != None and attr.potential < 0):
#             local_es = local_es * (-1) #avoid (-) * (-) = (+) scenario
#         es += local_es
#
#     return es

def get_attribute_averages() -> List[Tuple[str, float, float]]:
    averages = []
    for key, stats in attribute_explanation.items():
        count = stats["count"]
        avg_weight = stats["weight_sum"] / count
        avg_potential = stats["potential_sum"] / count
        averages.append((key, avg_weight, avg_potential))
    return averages

def open_csv(path):
    return pd.read_csv(path, header=None, sep='\n')


def save_results(results, out_dir, dataset, n_records, info_extra):
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)

    file_name = f"{dataset}_{n_records}_{info_extra}.txt"
    file_path = path / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(str(results))


def main(args):
    list_of_pairs = []
    nextProtected = True
    BASE_PATH = args[0] #"D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"
    k_ranking = int(args[1]) #20
    task = args[2] #'DBLP-GoogleScholar'
    lm= args[3] #"roberta"
    # k_batch = int(args[5]) #5742
    threshold = float(args[4])
    ranking_mode = args[7]
    matching_algorithm = args[8]
    explanation_flag = int(args[9]) #0: 'no explanation', 1: 'perform explanation with LEMON', 2: 'perform explanation with SHAP'
    # gpu = [int(i) for i in args[9].split("_")]
    # print("gpu: ", gpu)
    incremental_clusters = []

    if (explanation_flag > 0):
        if(ranking_mode != 'm-fair'):
            print("ERROR: Data Assessment component is just able for 'm-fair' ranking mode!")
            sys.exit()
        if(matching_algorithm != 'ditto'):
            print("ERROR: Data Assessment component is just able for 'ditto' matching mode!")
            sys.exit()



    results = {"top-5":[], "top-10":[],	"top-15":[], "top-20":[], "time_to_match":[], "time_to_rank":[], "time_to_explain":[], "total_time":[], "PPVP":[], "TPRP":[], "Bias":[], "ES":[], "Explanation":[]}

    with open(BASE_PATH + task + '/test.txt', encoding="utf8") as file:
        labed_file = [line.rstrip() for line in file]

    pairs_to_compare = open_csv(BASE_PATH + task + '/test.txt')

    if (matching_algorithm == 'ditto'):
        print('DITTO SELECTED')
        config, model, threshold, summarizer, dk_injector = setUpDitto(task="Structured/" + task, lm=lm, checkpoint_path="checkpoints/", threshold = threshold)
    elif (matching_algorithm == 'gnem'):
        useful_field_num = int(str(pairs_to_compare[0].iloc[0]).count('COL')/2)
        print("useful_field_num ", useful_field_num)
        model, embed_model, criterion = setUpGNEM(data=task, useful_field_num=useful_field_num)
        print('GNEM SELECTED')
    else:
        print('MATCHING ALGORITHM NOT AVAILABLE')
        exit(0)

    print("---- Ready to Consume ----")

    init = 0
    n_batches = int(args[5]) #5741
    window = n_batches - init
    pair_size = len(pairs_to_compare.index) - 1

    list_of_pairs = []

    increment = 0
    pairs_processed = 0
    while ((not pairs_to_compare.empty) and (init < pair_size)):#for i in range(0,len(preds.index)):
        lines = pairs_to_compare.loc[init:min(n_batches, pair_size)]
        reference = labed_file[0:min(n_batches, pair_size)]

        for row in lines.to_numpy():
            triple = row[0].split("\t")
            data = [triple[0], triple[1]]#.loc[i].to_json()
            list_of_pairs.append(data)

        init = n_batches + 1
        n_batches = init + (window) #if (n_batches + (window) < len(source.index)) else dataset_size
        print("pairs size: " + str(len(lines.index)))
        # n_batches = n_batches + (window)

        #perform data assessment and define the groups
        groups_data_assessment = []
        # if (data_assessment == 1): #if data assessment is required
        #     groups_data_assessment = data_assessment_menager.get_groups(lines, task)

        #call to match

        if (matching_algorithm == 'ditto'):
            #PERFORM DITTO
            pairs_processed = pairs_processed + len(list_of_pairs)
            print('RUNNING DITTO')
            if (explanation_flag > 0):
                clusters, preds, av_time, nextProtected, time_to_match, time_to_rank, exp, time_to_explain = match_rank_streaming_explantion(task, list_of_pairs, nextProtected, config, model, threshold, summarizer, dk_injector, lm, k_ranking, ranking_mode, explanation_flag, groups_data_assessment, incremental_clusters)
            else:
                clusters, preds, av_time, nextProtected, time_to_match, time_to_rank = match_rank_streaming(task, list_of_pairs, nextProtected, config, model, threshold, summarizer, dk_injector, lm, k_ranking, ranking_mode, groups_data_assessment)
        elif (matching_algorithm == 'gnem'):
            #PERFORM GNEM
            pairs_processed = pairs_processed + len(lines)
            print('RUNNING GNEM')
            clusters, av_time, nextProtected, time_to_match, time_to_rank = match_gnem_rank_streaming(task, lines, nextProtected, model, embed_model, criterion, k_ranking, ranking_mode)
        else:
            print('MATCHING ALGORITHM NOT AVAILABLE')
            exit(0)


        #EXPLANATION
        # for key in exp.keys():
        #     print(key)
        if (explanation_flag > 0):
            for item in exp.values():
                extract_attribute_tuples(item.attributions)
            current_explanation = get_attribute_averages();
            print("Current Explanation:")
            print(current_explanation)
            results["Explanation"].append(current_explanation)

            #Add explanation info to records
            clusters = add_explanation_info(clusters, exp)

        #RE-RANKING
        if ranking_mode == 'none':
            print("Skipping Ranking Step!")
            #merging the results
            incremental_clusters.extend(clusters)
            incremental_clusters.sort(key=sortBySimilarity, reverse=True)
            incremental_clusters = incremental_clusters[0:k_ranking]
        else:
            print("Starting Ranking Step!")
            if (explanation_flag > 0):
                print("Ranking Step with Explanation!")
                incremental_clusters = merge_clusters_with_explantion(clusters, incremental_clusters, k_ranking, ranking_mode)
            else:
                print("Ranking Step without Explanation!")
                incremental_clusters = merge_clusters(clusters, incremental_clusters, k_ranking, ranking_mode)
        list_of_pairs = []
        # current_dataframe_source.drop(current_dataframe_source.index, inplace=True)


        #RESULTS UPDATE
        if (explanation_flag > 0):
            results["time_to_explain"].append(time_to_explain)
            results["ES"].append(compute_EFS_average(incremental_clusters))
        results["time_to_match"].append(time_to_match)
        results["time_to_rank"].append(time_to_rank)
        results["total_time"].append(time_to_match + time_to_rank)

        print('clusters:')
        print(incremental_clusters)

        #evaluate effectivenss and fairness
        perform_evaluation(task, incremental_clusters, reference, results, ranking_mode)

        increment += 1
        print("Increments processed: " + str(increment))
        print("Pairs (processed): " + str(pairs_processed))
        print("time_to_match: " + str(results["time_to_match"]))
        print("time_to_rank: " + str(results["time_to_rank"]))
        print("time_to_explain: " + str(results["time_to_explain"]))
        print("total_time: " + str(results["total_time"]))
        print("ES: " + str(results["ES"]))

        time.sleep(int(args[6]))

    save_results(
        results=results,
        out_dir="treats_outputs_lemon",
        dataset=task,
        n_records=args[5],
        info_extra= {
            0: "TREATS",
            1: "LEMON",
            2: "SHAP"
        }.get(explanation_flag, "unknown explanation mode")
    )
    print(results)
    file.close()

if __name__ == '__main__':
    args = sys.argv[1:]
    print(args)
    main(args)