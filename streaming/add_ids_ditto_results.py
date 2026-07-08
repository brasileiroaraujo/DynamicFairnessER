import pandas as pd

path = "D:\\IntelliJ_Workspace\\fairER\\resources\\Datasets\\Beer"

df_ditto = pd.read_json(path_or_buf=path + '\output_small_beer.jsonl', lines=True)
df_left = pd.read_csv(path + '/tableA.csv')
df_right = pd.read_csv(path + '/tableB.csv')

#add left ids
name = df_ditto.left.str.split("COL", expand=True)[1].str.split("VAL", expand=True)[1]
name

# df_ditto = pd.concat([df_ditto,df_deep['id']], axis=1)

df_ditto.to_json(path + '\output_small_beer_ids.json', orient='records', lines=True)