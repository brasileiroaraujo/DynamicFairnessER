import matcher
import pandas as pd
from clustering import fair_unique_mapping_clustering as fumc
import util

def open_ditto_result(path):
    df = pd.read_json(path_or_buf=path, lines=True)

    if len(df) == 0: #check if df is empty
        return df

    df = pd.concat([df,extractLeftColumns(df)], axis=1)
    df = df.drop(axis=1, columns=["left"])

    df = pd.concat([df,extractRightColumns(df)], axis=1)
    df = df.drop(axis=1, columns=["right"])

    df.rename(columns={"match_confidence": 'match_score', "match": 'label'}, inplace=True)
    return df

def extractLeftColumns(df):
    df_splited = df.left.str.split("COL", expand=True)
    df_splited = df_splited.drop(axis=1, columns=[0])
    df_splited.rename(columns={1: 'left_Id', 2: 'left_Beer_Name', 3: 'left_Brew_Factory_Name', 4: 'left_Style', 5: 'left_ABV'}, inplace=True)

    df_splited['left_Id'] = df_splited['left_Id'].str.split("VAL", expand=True)[1]
    df_splited['left_Beer_Name'] = df_splited['left_Beer_Name'].str.split("VAL", expand=True)[1]
    df_splited['left_Brew_Factory_Name'] = df_splited['left_Brew_Factory_Name'].str.split("VAL", expand=True)[1]
    df_splited['left_Style'] = df_splited['left_Style'].str.split("VAL", expand=True)[1]
    df_splited['left_ABV'] = df_splited['left_ABV'].str.split("VAL", expand=True)[1]

    return df_splited

def extractRightColumns(df):
    df_splited = df.right.str.split("COL", expand=True)
    df_splited = df_splited.drop(axis=1, columns=[0])
    df_splited.rename(columns={1: 'right_Id', 2: 'right_Beer_Name', 3: 'right_Brew_Factory_Name', 4: 'right_Style', 5: 'right_ABV'}, inplace=True)

    df_splited['right_Id'] = df_splited['right_Id'].str.split("VAL", expand=True)[1]
    df_splited['right_Beer_Name'] = df_splited['right_Beer_Name'].str.split("VAL", expand=True)[1]
    df_splited['right_Brew_Factory_Name'] = df_splited['right_Brew_Factory_Name'].str.split("VAL", expand=True)[1]
    df_splited['right_Style'] = df_splited['right_Style'].str.split("VAL", expand=True)[1]
    df_splited['right_ABV'] = df_splited['right_ABV'].str.split("VAL", expand=True)[1]

    return df_splited

def open_csv(path):
    return pd.read_csv(path)

def cartesian_product(source, target):
    format_source = []
    for row_source in source.to_dict(orient='records'):
        content_source = ""
        for attr_source in row_source.keys():
            content_source += 'COL %s VAL %s ' % (attr_source, row_source[attr_source])
        format_source.append(content_source)

    format_target = []
    for row_target in target.to_dict(orient='records'):
        content_target = ""
        for attr_target in row_target.keys():
            content_target += 'COL %s VAL %s ' % (attr_target, row_target[attr_target])
        format_target.append(content_target)

    #return the pairs (cartesian among the lines)
    return [[s,t] for s in format_source for t in format_target]



print("--- Matching with Ditto ...  ---")
path_matches = "output/output_full_fair.jsonl"

#reading data
BASE_PATH = "D:\\IntelliJ_Workspace\\fairER\\resources\\Datasets"
source = open_csv(BASE_PATH + '\\Beer\\tableA.csv')
target = open_csv(BASE_PATH + '\\Beer\\tableB.csv')

#organizing the pairs (to be compared)
input_dataframe = cartesian_product(source, target)

#sending the pairs to be matched
matcher.run_matcher_streaming(task="Structured/Beer", input_dataframe=input_dataframe, output_path=path_matches, lm="roberta", checkpoint_path="checkpoints/")


print("--- SAFER Ranking ...  ---")
preds = open_ditto_result(path_matches)


def save_file(clusters):
    # f = open('output/clusters.txt', 'w')

    with open('output/clusters.txt', 'w') as f:
        for pair in clusters[0]:
            f.write('%s\n' % pair)
    # for t in clusters:
    #     line = ' '.join(x for x in t)
    #     f.write(line + '\n')
    f.close()


if len(preds) > 0:
    preds = preds.sort_values(by='match_score', ascending=False)

    initial_pairs = [(a.left_Id, a.right_Id, a.match_score, util.pair_is_protected(a, "Beer", False))
                     for a in preds.itertuples(index=False)] #Ditto

    k_results = 20
    clusters = fumc.run_steraming(initial_pairs, True, k_results)
    print("\nclustering results:\n", clusters)
    save_file(clusters)

else:
    print("\nNo matches detected.\n")