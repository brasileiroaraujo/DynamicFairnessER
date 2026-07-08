import pandas as pd

BASE_PATH = "D:/IntelliJ_Workspace/fairER/resources/Datasets"
source = pd.read_csv(BASE_PATH + '\\Beer\\tableA.csv', header=0)
target = pd.read_csv(BASE_PATH + '\\Beer\\tableB.csv', header=0)

test_file = pd.read_csv(BASE_PATH + '\\Beer\\test.csv', header=0)

new_source = pd.DataFrame(columns=source.columns)
new_target = pd.DataFrame(columns=target.columns)

for index, row in test_file.iterrows():
    new_source = new_source.append(source.loc[source['id'] == int(row['ltable_id'])])
    new_target = new_target.append(target.loc[source['id'] == int(row['rtable_id'])])
    # print(row['ltable_id'], row['rtable_id'], row['label'])

# new_source = new_source.append(source.loc[source['id'] == 4161])

# print(new_source)
# print(new_target)
#
# new_source.to_csv(BASE_PATH + '\\Beer\\tableA_test.csv', index=False)
# new_target.to_csv(BASE_PATH + '\\Beer\\tableB_test.csv', index=False)

#TO PRINT THE NAMES WHERE LABEL IS 1, THE GOLDSTANDARD
for index, row in test_file.iterrows():
    if row['label'] == 1:
        print(str(source.loc[source['id'] == int(row['ltable_id'])]['Beer_Name'].item()) + " <==> " + str(target.loc[source['id'] == int(row['rtable_id'])]['Beer_Name'].item()))
