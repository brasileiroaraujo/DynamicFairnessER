import pygsheets
from ditto_light.dataset import DittoDataset
from tqdm import tqdm
from torch.utils import data


print("lyman do , prabhu ram , pamela drew".split(
    ",")[-1].strip().split(" ")[0].replace('.', ''))

# tuple = 'xxx monitors Red only'
#
# default_conditions = {'Amazon-Google': "('microsoft' in str(tuple.left_manufacturer)) or ('microsoft' in str(tuple.right_manufacturer))",
#                       'Beer': "1 if ('Red' in str(tuple)) or ('Red' in str(tuple)) else 0",
#                       'DBLP-ACM': "('female' in d.get_gender(last_author_fname_l)) or ('female' in d.get_gender(last_author_fname_r))",
#                       'DBLP-GoogleScholar': "('vldb j' in str(tuple.left_venue)) or ('vldb j' in str(tuple.right_venue))",
#                       'Fodors-Zagats': "('asian' == str(tuple.left_entity_type)) or ('asian' == str(tuple.right_entity_type))",
#                       'iTunes-Amazon': "1 if ('Dance' in tuple) or ('Dance' in tuple) else 0",
#                       'Walmart-Amazon': "1 if (('printers' in tuple) or ('printers' in tuple))"
#                                         "else 2 if (('laptop' in tuple) or ('laptop' in tuple))"
#                                         "else 3 if (('monitors' in tuple) or ('monitors' in tuple))"
#                                         "else 0"}
#
# index = eval(default_conditions['Beer'])
#
# # print(index)
#
# x = {0:'a',
#      1:'b',
#      2:'c'}
# print(x.get(5))
# print(max(x.keys()))
# print(range(max(x.keys())))
#
#
# DATASET = 'iTunes-Amazon'
# TEST_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/" + DATASET + "/test.txt"
# with open(TEST_PATH, encoding="utf8") as file:
#     goldstandard = [line.rstrip() for line in file]
#
# dataset = DittoDataset(goldstandard,
#                        max_len=256,
#                        lm='roberta')
#
# iterator = data.DataLoader(dataset=dataset,
#                            batch_size=len(dataset),
#                            shuffle=False,
#                            num_workers=0,
#                            collate_fn=DittoDataset.pad)
#
# for i, batch in enumerate(iterator):
#     print(i, batch)
#
#
# x = list(range(0, 4))
# print(x)
# x.pop(2)
# print(x)
# print(x[2])



# client = pygsheets.authorize(client_secret='C:/Users/admin/Desktop/STREAMING+FAIRNESS RESULTS/client_secret_914606524472-d3pdv2h83599j5gjrbv1u9lhgn2fs428.apps.googleusercontent.com.json')
# # Open the spreadsheet and the first sheet.
# sh = client.open('FairnessResults')
# wks = sh.sheet1
# # Update a single cell.
# wks.update_value('A85', "Numbers on Stuff")
# Update the worksheet with the numpy array values
#
# x = {}
#
#
# def add_protected_group(dict_groups, index, tuple):
#     if dict_groups.get(index) == None:
#         dict_groups[index]=[tuple]
#     else:
#         dict_groups.get(index).append(tuple)
#
#
# add_protected_group(x, index, tuple)
# add_protected_group(x, index, "2")
#
#
# print(x)
# x = {}
#
#
# def add_protected_group(dict_groups, index, tuple):
#     if dict_groups.get(index) == None:
#         dict_groups[index]=[tuple]
#     else:
#         dict_groups.get(index).append(tuple)
#
#
# add_protected_group(x, index, tuple)
# add_protected_group(x, index, "2")
#
#
# print(x)