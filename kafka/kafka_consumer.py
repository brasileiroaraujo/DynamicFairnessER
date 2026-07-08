from confluent_kafka import Consumer
import pandas as pd
import json
import evaluation.accuracy as eval
import time
from streaming.controller_fairER_streaming import match_streaming

################

c=Consumer({'bootstrap.servers':'localhost:9092','group.id':'python-consumer','auto.offset.reset':'earliest'})

print('Available topics to consume: ', c.list_topics().topics)

c.subscribe(['user-tracker'])

################

def main():
    current_dataframe = pd.DataFrame()
    nextProtected = True
    while True:
        msg=c.poll(1.0) #timeout
        if msg is None:
            continue
        if msg.error():
            print('Error: {}'.format(msg.error()))
            continue
        data_json = json.loads(msg.value().decode('utf-8'))
        data_frame = pd.json_normalize(data_json)

        if(not data_frame.empty):
            current_dataframe = current_dataframe.append(data_frame)
            print('row:')
            print(data_frame)
            clusters, current_dataframe, av_time, nextProtected = match_streaming('Beer', current_dataframe, nextProtected)
            data_frame.drop(data_frame.index, inplace=True)

            #############################
            # Evaluation
            #############################
            print("--- %s seconds ---" % (av_time / 10.0))

            if (clusters):
                accuracy = eval.get_accuracy(clusters, current_dataframe)
                print("accuracy:", accuracy)

    c.close()

if __name__ == '__main__':
    main()