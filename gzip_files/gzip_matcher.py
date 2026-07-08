import gzip
import time
import pandas as pd

def extract(row):
    tokens = []
    for val in row.split("COL"):
        if len(val) > 0:
            tokens.append(val.split("VAL")[1])
    return tokens

def compute_similarity(tokens_left, tokens_right):
    sim = 0.0
    for i in range(0,4):
        x1 = tokens_left[i]
        x2 = tokens_right[i]

        Cx1 = len(gzip.compress(x1.encode()))
        Cx2 = len(gzip.compress(x2.encode()))

        x1x2= " ".join([x1,x2])

        Cx1x2=len(gzip.compress(x1x2. encode()))

        ncd=(Cx1x2-min(Cx1,Cx2))/ max(Cx1,Cx2)


        sim = sim + ncd
        # if (ncd < 0.36):
        #     print(triple[0] + " - " + triple[1])
        #     print(str(ncd) + " - " + str(triple[2]))
    return sim/4

def gzip_matching_ranking(list_of_pairs):
    result = {'left': [],
              'right': [],
              'match_score': []}

    ###########
    # Matching with GZIP
    ###########
    print("--- Matching with GZIP ...  ---")
    start_time = time.time()
    for pairs in list_of_pairs:
        tokens_left = extract(pairs[0])
        tokens_right = extract(pairs[1])
        sim = compute_similarity(tokens_left, tokens_right)

        result.get('left').append(tokens_left)
        result.get('right').append(tokens_right)
        result.get('match_score').append(sim)
    print('Time to match: ' + str(time.time() - start_time))

    preds = pd.DataFrame(result)
    preds = preds.sort_values(by='match_score', ascending=True)

    BASE_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"
    preds.head(20).to_csv(BASE_PATH + 'gzip_out.csv', index=False)

    return preds