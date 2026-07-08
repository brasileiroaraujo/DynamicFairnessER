import torch

print(torch.__version__)
print(torch.cuda.is_available())
# import pandas as pd
#
# pairs_to_compare = pd.read_csv("data/er_magellan/Structured/Amazon-Google/test.txt", header=None, sep='\n')
# lines = pairs_to_compare.loc[0:100]
#
# for i in lines.to_numpy():
#     i = i[0]
#     print("line ", i)

# row1 = str(pairs_to_compare[0].iloc[0])
# print(row1)
# useful_field_num = int(str(pairs_to_compare[0].iloc[0]).count('COL')/2) #TODO: VALIDATE THIS COMPUTATION
# print("useful_field_num ", useful_field_num)