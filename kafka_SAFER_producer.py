from confluent_kafka import Producer
from faker import Faker
import json
import time
import logging
import sys
import random
import pandas as pd
from blocking import token_blocking


def receipt(err,msg):
    if err is not None:
        print('Error: {}'.format(err))
    else:
        message = 'Produced message on topic {} with value of {}\n'.format(msg.topic(), msg.value().decode('utf-8'))
        # logger.info(message)
        print(message)

#####################
print('Kafka Producer has been initiated...')

BASE_PATH = "D:/IntelliJ_Workspace/fairER/resources/Datasets"

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
    return [s + "SEPARATOR" + t for s in format_source for t in format_target]

def configure_line(id_kb, kb):
    format_source = []
    tokens = set()
    for row_source in kb.to_dict(orient='records'):
        content_source = ""
        for attr_source in row_source.keys():
            content_source += 'COL %s VAL %s ' % (attr_source, row_source[attr_source])
            tokens = tokens.union(set(token_blocking.extract_tokens(row_source[attr_source])))
        tokens = token_blocking.extract_tokens(str(tokens)) #organize the top-5 tokens
        format_source.append(content_source + ' TOKEN ' + str(tokens).replace("[", "").replace("]",""))
        tokens = set()

    return [str(id_kb) + s for s in format_source]

def main():
    p = Producer({'bootstrap.servers':'localhost:9092'})

    source = open_csv(BASE_PATH + '\\Beer\\tableA_test.csv')
    source = source.drop(['id'], axis=1) #id will ignore for ditto
    target = open_csv(BASE_PATH + '\\Beer\\tableB_test.csv')
    target = target.drop(['id'], axis=1) #id will ignore for ditto

    init = 0
    n_batches = 90
    window = n_batches - init
    source_size = len(source.index) - 1
    target_size = len(target.index) - 1
    dataset_size = max(source_size, target_size)

    while ((not source.empty) and (not target.empty) and (init < source_size and init < target_size)):#for i in range(0,len(preds.index)):
        # line = preds.loc[0]#.to_json()
        lines_s = configure_line(1, source.loc[init:min(n_batches, source_size)])
        lines_t = configure_line(2, target.loc[init:min(n_batches, target_size)])

        # pairs = cartesian_product(lines_s, lines_t)

        # print(lines.loc[0].to_json())
        entities_to_send = lines_s + lines_t

        for line in entities_to_send:#for i in range(init,n_batches+1):
            p.poll(1)
            #line = pairs[i]#.loc[i].to_json()
            print(line)
            p.produce('safer', line.encode('utf-8'),callback=receipt)
        p.flush()

        init = n_batches + 1
        n_batches = init + (window) #if (n_batches + (window) < len(source.index)) else dataset_size
        print("source size: " + str(len(lines_s)))
        print("target size: " + str(len(lines_t)))
        # n_batches = n_batches + (window)

        time.sleep(60)


        # for i in range(0,len(preds.index)):
        #     line = preds.loc[i].to_json()
        # p.poll(1)
        # p.produce('user-tracker', line.encode('utf-8'),callback=receipt)
        # p.flush()
        # time.sleep(60)

    # m=json.dumps(data)


if __name__ == '__main__':
    main()