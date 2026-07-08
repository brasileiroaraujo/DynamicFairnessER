import matcher
import pandas as pd
from clustering import fair_unique_mapping_clustering as fumc
import util

def open_ditto_result(path):
    df = pd.read_json(path_or_buf=path, lines=True)

    df = pd.concat([df,extractLeftColumns(df)], axis=1)
    df = df.drop(axis=1, columns=["left"])

    df = pd.concat([df,extractRightColumns(df)], axis=1)
    df = df.drop(axis=1, columns=["right"])

    df.rename(columns={"match_confidence": 'match_score', "match": 'label'}, inplace=True)
    return df

def extractLeftColumns(df):
    df_splited = df.left.str.split("COL", expand=True)
    df_splited = df_splited.drop(axis=1, columns=[0])
    df_splited.rename(columns={1: 'left_Beer_Name', 2: 'left_Brew_Factory_Name', 3: 'left_Style', 4: 'left_ABV'}, inplace=True)

    df_splited['left_Beer_Name'] = df_splited['left_Beer_Name'].str.split("VAL", expand=True)[1]
    df_splited['left_Brew_Factory_Name'] = df_splited['left_Brew_Factory_Name'].str.split("VAL", expand=True)[1]
    df_splited['left_Style'] = df_splited['left_Style'].str.split("VAL", expand=True)[1]
    df_splited['left_ABV'] = df_splited['left_ABV'].str.split("VAL", expand=True)[1]

    return df_splited

def extractRightColumns(df):
    df_splited = df.right.str.split("COL", expand=True)
    df_splited = df_splited.drop(axis=1, columns=[0])
    df_splited.rename(columns={1: 'right_Beer_Name', 2: 'right_Brew_Factory_Name', 3: 'right_Style', 4: 'right_ABV'}, inplace=True)

    df_splited['right_Beer_Name'] = df_splited['right_Beer_Name'].str.split("VAL", expand=True)[1]
    df_splited['right_Brew_Factory_Name'] = df_splited['right_Brew_Factory_Name'].str.split("VAL", expand=True)[1]
    df_splited['right_Style'] = df_splited['right_Style'].str.split("VAL", expand=True)[1]
    df_splited['right_ABV'] = df_splited['right_ABV'].str.split("VAL", expand=True)[1]

    return df_splited

print("--- Matching with Ditto ...  ---")
path_matches = "output/output_small_test_fair.jsonl"
matcher.run_matcher_batch(task="Structured/Beer", input_path="data/er_magellan/Structured/Beer/test.txt", output_path=path_matches, lm="roberta", checkpoint_path="checkpoints/")

preds = open_ditto_result(path_matches)

preds = preds.sort_values(by='match_score', ascending=False)

initial_pairs = [(a.left_Beer_Name, a.right_Beer_Name, a.match_score, util.pair_is_protected(a, "Beer", False))
                 for a in preds.itertuples(index=False)] #Ditto

k_results = 20
clusters = fumc.run(initial_pairs, k_results)
print("\nclustering results:\n", clusters)