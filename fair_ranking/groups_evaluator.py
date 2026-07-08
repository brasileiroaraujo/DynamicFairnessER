#Class to evaluate the diversity in protected attributes
import yake

from evaluation import decompose_col_val

language = "en"
max_ngram_size = 1
num_keywords = 1
custom_kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, top=num_keywords)

TEST_PATH = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/DBLP-GoogleScholar/test.txt"

def extractValue(tuple, attribute_name):
    values_by_attribute = tuple.split(attribute_name + " VAL ")
    return values_by_attribute[1].split("COL")[0], values_by_attribute[2].split("COL")[0]

def getToken(text):
    language = "en"
    max_ngram_size = 1
    num_keywords = 1
    custom_kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, top=num_keywords)

    return [kw[0] for kw in custom_kw_extractor.extract_keywords(text)]

with open(TEST_PATH, encoding="utf8") as file:
    candidates = [line.rstrip() for line in file]

left_values = []
right_values = []
pairs = []
for i in candidates:
    if i[len(i) - 1] == '1':
        left, right = extractValue(i, "venue")
        if len(getToken(left)) > 0: left_values.append(getToken(left)[0])
        if len(getToken(right)) > 0: right_values.append(getToken(right)[0])

        df = decompose_col_val.decompose_srt_to_df(i)
        pairs.append(df.left_venue[0] + ' - ' + df.right_venue[0])


#Summary
print("left size: " + str(len(left_values)))
print("right size: " + str(len(right_values)))

print("---- Left ----")
for i in left_values:
    if i in right_values:
        print(i)

print("---- Right ----")
for i in right_values:
    print(i)

print("---- Pairs ----")
print(len(pairs))
for i in pairs:
    if not ("vldb" in i or "sigmod" in i):
        print(i)