from confluent_kafka import Consumer
import pandas as pd
import json
import evaluation.accuracy as eval
import time
from streaming.controller_fairER_streaming import match_streaming
from streaming.controller_fairER_streaming import match_rank_streaming
from blocking import token_blocking
import matcher

################

cs=Consumer({'bootstrap.servers':'localhost:9092','group.id':'python-consumer','auto.offset.reset':'earliest'})

print('Available topics to consume: ', cs.list_topics().topics)

cs.subscribe(['safer'])

def setUpDitto(task, lm="distilbert", use_gpu="store_true", fp16="store_true",
               checkpoint_path='checkpoints/', dk=None, summarize="store_true", max_len=256):
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
    print("---- Tuning Threshold ----")
    threshold = matcher.tune_threshold_parameterized(config, model, task, summarize, lm, max_len, dk)
    print('APPLIED THRESHOLD: ' + str(threshold))

    print("---- Ditto Configured ----")

    return config, model, threshold, summarizer, dk_injector

def sortBySimilarity(element):
    return float(element[2])

def merge_clusters(clusters, incremental_clusters, k_ranking):
    incremental_clusters.extend(clusters[0])
    incremental_clusters.sort(key=sortBySimilarity, reverse=True)
    return fairness_ranking(incremental_clusters, True, k_ranking)

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


def main():
    list_of_pairs = []
    nextProtected = True
    k_ranking = 20
    task = 'Beer'
    lm="roberta"
    k_batch = 91
    incremental_clusters = []
    list_of_entities_source = []
    list_of_entities_target = []

    config, model, threshold, summarizer, dk_injector = setUpDitto(task="Structured/" + task, lm=lm, checkpoint_path="checkpoints/")

    print("---- Ready to Consume ----")

    while True:
        msg_s=cs.poll(1.0) #timeout
        # msg_t=ct.poll(1.0)
        if msg_s is None:
            continue
        if msg_s.error():
            print('Error: {}'.format(msg_s.error()))
            continue

        entity_string = msg_s.value().decode('utf-8')
        if entity_string[0] == '1':
            list_of_entities_source.append(entity_string[1:])#remove the label of source
        else:
            list_of_entities_target.append(entity_string[1:])#remove the label of target

        #TODO: it should be a window time
        if len(list_of_entities_source) == k_batch and len(list_of_entities_target) == k_batch:
            #perform blocking
            print('\n', 'Token Blocking processing ... ', '\n')
            start_time = time.time()
            list_of_pairs = token_blocking.run(list_of_entities_source, list_of_entities_target, k_batch)
            print('\n', 'Token Blocking finished ... ' + str(time.time() - start_time) + ' (sec)', '\n')

            # print('PAIRS TO COMPARE:')
            # print(list_of_pairs)

            list_of_pairs = [pair.split("SEPARATOR") for pair in list_of_pairs]

            clusters, preds, av_time, nextProtected = match_rank_streaming(task, list_of_pairs, nextProtected, config, model, threshold, summarizer, dk_injector, lm, k_ranking)
            incremental_clusters = merge_clusters(clusters, incremental_clusters, k_ranking)
            list_of_pairs = []
            # current_dataframe_source.drop(current_dataframe_source.index, inplace=True)

            print('clusters:')
            print(incremental_clusters)


    cs.close()

if __name__ == '__main__':
    main()