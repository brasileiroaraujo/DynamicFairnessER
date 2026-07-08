import gzip
import numpy as np
import pandas as pd
import time

def open_csv(path):
    return pd.read_csv(path, header=None, sep='\n')

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

def evaluate_similarity(sim):
    for i in sim:
        if (i > 0.40):
            return False
    return True

print("--- Matching with GZIP ...  ---")
start_time = time.time()

BASE_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"
pairs_to_compare = open_csv(BASE_PATH + 'Walmart-Amazon/test.txt').to_numpy()


result = {'left': [],
        'right': [],
        'match_score': [],
        'label': []}


for row in pairs_to_compare:
    triple = row[0].split("\t")
    tokens_left = extract(triple[0])
    tokens_right = extract(triple[1])
    sim = compute_similarity(tokens_left, tokens_right)


    result.get('left').append(tokens_left)
    result.get('right').append(tokens_right)
    result.get('match_score').append(sim)
    result.get('label').append(triple[2])
    # print(str(tokens_left) + " - " + str(tokens_right) + " : " + str(sim) + " | " + triple[2])

preds = pd.DataFrame(result)
preds = preds.sort_values(by='match_score', ascending=True)
preds.head(20).to_csv(BASE_PATH + 'gzip_DBLP-GoogleScholar.csv', index=False)

print('Time to match: ' + str(time.time() - start_time))