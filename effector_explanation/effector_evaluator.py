import numpy as np
import effector
import time
import matcher
import pandas as pd

import decompose_col_val


def load_model_ditto(task, lm="distilbert", use_gpu=False, fp16=False,
                     checkpoint_path='checkpoints/'):
    matcher.set_seed(123)
    config, model = matcher.load_model(task, checkpoint_path,
                                       lm, use_gpu, fp16)
    return model


def open_csv(path):
    return pd.read_csv(path, header=None, sep='\n').to_numpy()


def open_csv2(path):
    list_of_pairs = []
    lines = pd.read_csv(path, header=None, sep='\n').to_numpy()
    for line in lines:
        df, label, left_id, right_id = decompose_col_val.decompose_srt_to_full_df(line[0])
    return df


BASE_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/"
task = 'DBLP-GoogleScholar'
pairs_to_compare = open_csv2(BASE_PATH + task + '/test.txt')
# model = load_model_ditto("D:/IntelliJ_Workspace/fairER/checkpoints/Structured/" + task + "/model.pt")
model_ditto = load_model_ditto(task="Structured/" + task, checkpoint_path="D:/IntelliJ_Workspace/fairER/checkpoints/",
                               lm='roberta')

print(type(pairs_to_compare.to_numpy()))  # should be numpy.ndarray
print(pairs_to_compare)

print("-----Starting Effector-----")

effector.RegionalPDP(pairs_to_compare.to_numpy(), model_ditto).show_partitioning(features=0)

# pdp = effector.PDP(pairs_to_compare, model).plot(feature=0)
# regional_pdp = effector.RegionalPDP(data=pairs_to_compare, model=model)

# pdp = effector.PDP(data=pairs_to_compare, model=model_forward)
# regional_pdp.fit(features="all", heter_pcg_drop_thres=0.3, nof_candidate_splits_for_numerical=11, centering=True)


# regional_pdp.show_partitioning(features=0)
# print('===================================')
# regional_pdp.show_partitioning(features=1)
# print('===================================')
# regional_pdp.show_partitioning(features=2)
# print('===================================')
