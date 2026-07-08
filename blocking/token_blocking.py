import yake


def blocking(entities, token_map, is_source):
    for e in entities:
        print(e)
        ent_token = e.split("TOKEN")
        for key in ent_token[1].split(","):
            key = key.strip()
            ent_tuple = token_map.get(key)
            if (ent_tuple == None):
                if is_source:
                    token_map.update([(key, [[ent_token[0].strip()], []])]) #the format is (key, list_source, list_target)
            else:
                if is_source:
                    ent_tuple[0].append(ent_token[0].strip())
                    token_map.update([(key, ent_tuple)])
                else:
                    ent_tuple[1].append(ent_token[0].strip())
                    token_map.update([(key, ent_tuple)])


def filter_empty_target(token_map):
    key_to_delete = [key for key in token_map if not token_map.get(key)[1]]
    for key in key_to_delete:
        del token_map[key]

def filter_useless_blocks(token_map, k_batch):
    cut_value = k_batch/2
    key_to_delete = [key for key in token_map if (len(token_map.get(key)[0]) > cut_value or len(token_map.get(key)[1]) > cut_value)]
    for key in key_to_delete:
        del token_map[key]

def cartesian_product(source, target):
    #return the pairs (cartesian among the lines)
    return [s + "SEPARATOR" + t for s in source for t in target]

def run(source, target, k_batch):
    token_map = {}
    blocking(source, token_map, True)
    blocking(target, token_map, False)

    filter_empty_target(token_map)
    filter_useless_blocks(token_map, k_batch)

    list_of_pairs = set()
    for values in token_map.values():
        list_of_pairs = list_of_pairs.union(cartesian_product(values[0], values[1]))

    return list_of_pairs

def extract_tokens(text):
    language = "en"
    max_ngram_size = 1
    num_keywords = 5
    custom_kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, top=num_keywords)

    return [kw[0] for kw in custom_kw_extractor.extract_keywords(text)]

# source = ["1COL id VAL 0 COL Beer_Name VAL TrÃ ¶ egs Nugget Nectar COL Brew_Factory_Name VAL TrÃ ¶ egs Brewing Company COL Style VAL American Amber / Red Ale COL ABV VAL 7.50 %  TOKEN 'Company', 'Ale', 'egs', 'Nugget', 'Nectar', 'Brewing', 'Amber', 'American', 'Red', 'TrÃ'",
# "1COL id VAL 1 COL Beer_Name VAL Fat Tire Amber Ale COL Brew_Factory_Name VAL New Belgium Brewing COL Style VAL American Amber / Red Ale COL ABV VAL 5.20 %  TOKEN 'Company', 'Ale', 'egs', 'Tire', 'Nugget', 'Belgium', 'Nectar', 'Brewing', 'Amber', 'American', 'Fat', 'Red', 'TrÃ'"]
#
# target = ["2COL id VAL 0 COL Beer_Name VAL Great Lakes Nosferatu COL Brew_Factory_Name VAL Great Lakes Brewing &#40; Ohio &#41; COL Style VAL American Strong Ale COL ABV VAL 8 %  TOKEN 'Great', 'Ale', 'Nosferatu', 'Ohio', 'Lakes', 'Brewing', 'American', 'Strong'",
#           "2COL id VAL 1 COL Beer_Name VAL 4 Hands Reprise Centennial Red Ale COL Brew_Factory_Name VAL 4 Hands Brewing Company COL Style VAL Amber Ale COL ABV VAL 6 %  TOKEN 'Great', 'Ale', 'Company', 'Reprise', 'Nosferatu', 'Ohio', 'Centennial', 'Lakes', 'Brewing', 'Amber', 'American', 'Strong', 'Red', 'Hands'"]
#
#
# print(run(source, target))




