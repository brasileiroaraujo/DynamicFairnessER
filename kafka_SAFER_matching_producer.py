from confluent_kafka import Producer
from faker import Faker
import json
import time
import logging
import sys
import random
import pandas as pd

# fake=Faker()
#
# logging.basicConfig(format='%(asctime)s %(message)s',
#                     datefmt='%Y-%m-%d %H:%M:%S',
#                     filename='producer.log',
#                     filemode='w')
#
# logger = logging.getLogger()
# logger.setLevel(logging.INFO)



#####################

def receipt(err,msg):
    if err is not None:
        print('Error: {}'.format(err))
    else:
        message = 'Produced message on topic {} with value of {}\n'.format(msg.topic(), msg.value().decode('utf-8'))
        # logger.info(message)
        print(message)

#####################
print('Kafka Producer has been initiated...')

BASE_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"


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
    return pd.read_csv(path, header=None, sep='\n')

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

def main():
    p = Producer({'bootstrap.servers':'localhost:9092'})

    pairs_to_compare = open_csv(BASE_PATH + 'Beer/test.txt')#'Beer/test.txt')
    init = 0
    n_batches = 90
    window = n_batches - init
    pair_size = len(pairs_to_compare.index) - 1

    while ((not pairs_to_compare.empty) and (init < pair_size)):#for i in range(0,len(preds.index)):
        lines = pairs_to_compare.loc[init:min(n_batches, pair_size)]

        for row in lines.to_numpy():
            p.poll(1)
            triple = row[0].split("\t")
            data = triple[0] + "SEPARATOR" + triple[1]#.loc[i].to_json()
            print(data)
            p.produce('safer', data.encode('utf-8'),callback=receipt)
        p.flush()

        init = n_batches + 1
        n_batches = init + (window) #if (n_batches + (window) < len(source.index)) else dataset_size
        print("pairs size: " + str(len(lines.index)))
        # n_batches = n_batches + (window)

        time.sleep(30)

    # m=json.dumps(data)


if __name__ == '__main__':
    main()