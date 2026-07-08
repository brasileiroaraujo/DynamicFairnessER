import lemon
import torch
import torch.nn.functional as F
from matcher import classify, to_str
import matcher as m
from tqdm import tqdm
import pandas as pd

from SAFER_run_gpu import setUpDitto, open_csv

#data pre processing
# max_len = 256
# list_of_pairs = []
# pairs = []
# lines = pairs_to_compare.loc[0:1]
# for row in lines.to_numpy():
#     triple = row[0].split("\t")
#     data = [triple[0], triple[1]]#.loc[i].to_json()
#     list_of_pairs.append(data)
#
# for row in tqdm(list_of_pairs):
#     pairs.append(to_str(row[0], row[1], summarizer, max_len, dk_injector))
#
# predictions, logits = classify(pairs, model, lm=lm,
#                                max_len=max_len,
#                                threshold=threshold)

task = 'Amazon-Google'
lm= "roberta"
BASE_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"
pairs_to_compare = open_csv(BASE_PATH + task + '/test.txt')
config, model, threshold, summarizer, dk_injector = setUpDitto(task="Structured/" + task, lm=lm, checkpoint_path="checkpoints/", threshold = 0.2)

df1 = pd.read_csv('D:/IntelliJ_Workspace/GNEM/data/amazon_google/tableA.csv')
df2 = pd.read_csv('D:/IntelliJ_Workspace/GNEM/data/amazon_google/tableB.csv')
test_id_pairs = pd.read_csv('D:/IntelliJ_Workspace/GNEM/data/amazon_google/test.csv')
test_id_pairs = test_id_pairs.rename(columns={'ltable_id': 'a.rid', 'rtable_id': 'b.rid'})
test_id_pairs = test_id_pairs.drop(columns=['label'])
test_id_pairs.index.name = "pid"

# print(m.ditto_predict_proba(df1, df2, test_id_pairs.iloc[0:2], model))

print("TEST SET")
print(test_id_pairs.iloc[0:2])

exp = lemon.explain(
    df1,
    df2,
    test_id_pairs.iloc[0:2],
    lambda a, b, p: m.ditto_predict_proba(a, b, p, model=model),
    granularity="attributes"
    # explain_attrs=True
    # dual_explanation=False
    # attribution_method="shap",
    # estimate_potential=False
)

for item in exp.values():
    print(item.string_representation)
    print("----------------")
    print(item.attributions)
    # print("----------------")
    # print(item.metadata)
    # print("----------------")
    # print(item.record_pair)
    # print("----------------")
    # print(item.dual)
    # print("----------------")
    # print(item.prediction_score)
    print("----------------")

    print(item.as_html())
    ax, plt = item.plot_treats("both")
    plt.show()


