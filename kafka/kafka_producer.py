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

BASE_PATH = "D:\\IntelliJ_Workspace\\fairER\\resources\\Datasets"

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

def main():
    p = Producer({'bootstrap.servers':'localhost:9092'})

    preds = open_ditto_result(BASE_PATH + '\Beer\output_small_test2.jsonl')
    init = 0
    n_batches = 19
    dataset_size = len(preds.index) - 1

    while (not preds.empty and n_batches < dataset_size):#for i in range(0,len(preds.index)):
        # line = preds.loc[0]#.to_json()
        lines = preds.loc[init:n_batches]

        # print(lines.loc[0].to_json())

        for i in range(init,n_batches+1):
            p.poll(1)
            line = lines.loc[i].to_json()
            p.produce('user-tracker', line.encode('utf-8'),callback=receipt)
        p.flush()

        window = n_batches - init
        init = n_batches
        n_batches = n_batches + (window) if (n_batches + (window) < len(preds.index)) else dataset_size
        print(n_batches)
        # n_batches = n_batches + (window)

        time.sleep(2)


        # for i in range(0,len(preds.index)):
        #     line = preds.loc[i].to_json()
        # p.poll(1)
        # p.produce('user-tracker', line.encode('utf-8'),callback=receipt)
        # p.flush()
        # time.sleep(60)

    # m=json.dumps(data)


if __name__ == '__main__':
    main()