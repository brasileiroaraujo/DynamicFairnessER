import os
import pickle

import gender_guesser.detector as gender
# import web.library.methods as methods

d = gender.Detector(case_sensitive=False)  # to avoid creating many Detectors


def protectedCond(dataset, explanation):
    data = {}
    if explanation == 0:
        pickle_path = os.path.join('data', 'pickle_data', 'protected_conditions.pkl')
    else:
        pickle_path = os.path.join('data', 'pickle_data', 'protected_conditions_w_exp.pkl')
    curr_dir = os.path.split(os.getcwd())[1]
    if curr_dir == 'fairER':
        pickle_path = 'web/' + pickle_path
    if os.path.exists(pickle_path) and os.path.getsize(pickle_path) > 0:
        with open(pickle_path, 'rb') as pkl_file:
            data = pickle.load(pkl_file)

    condition = data.get(dataset)
    return condition

    # returns True if the given value (assumed to be coming from the protected attribute) is considered protected
    # if return_condition is True, the condition will be returned as string
def pair_is_protected(tuple=None, dataset=None, return_condition=False, explanation=0):
   
    if(return_condition):
        return default_conditions.get(dataset) if protectedCond(dataset,0) is None else protectedCond(dataset,0)
    else:
        try:
            if dataset == 'DBLP-ACM':
                last_author_fname_l = str(tuple.ltable_authors).split(
                    ",")[-1].strip().split(" ")[0].replace('.', '')
                last_author_fname_r = str(tuple.rtable_authors).split(
                    ",")[-1].strip().split(" ")[0].replace('.', '')
                last_author_is_female = ('female' in d.get_gender(last_author_fname_l)) or \
                    ('female' in d.get_gender(last_author_fname_r))

                return last_author_is_female
            else:
                return eval(default_conditions_w_exp[dataset]) if protectedCond(dataset,1) is None else eval(protectedCond(dataset,1))
        except AttributeError:
            if dataset == 'DBLP-ACM':
                last_author_fname_l = str(tuple.left_authors).split(
                    ",")[-1].strip().split(" ")[0].replace('.', '')
                last_author_fname_r = str(tuple.right_authors).split(
                    ",")[-1].strip().split(" ")[0].replace('.', '')
                last_author_is_female = ('female' in d.get_gender(last_author_fname_l)) or \
                    ('female' in d.get_gender(last_author_fname_r))

                return last_author_is_female
            else:
                return eval(default_conditions[dataset]) if protectedCond(dataset,0) is None else eval(protectedCond(dataset,0))

def pair_is_protected_by_group(tuple=None, dataset=None, return_condition=False, explanation=0):
    if dataset == 'DBLP-ACM':
        last_author_fname_l = str(tuple.left_authors).split(
            ",")[-1].strip().split(" ")[0].replace('.', '')
        last_author_fname_r = str(tuple.right_authors).split(
            ",")[-1].strip().split(" ")[0].replace('.', '')
        last_author_is_female = ('female' in d.get_gender(last_author_fname_l)) or \
                                ('female' in d.get_gender(last_author_fname_r))

        return 1 if last_author_is_female else 0 #0 always is the regular group, >=1 are the protected groups
    else:
        return eval(default_conditions_multiple_groups[dataset]) #if methods.protectedCond(dataset,0) is None else eval(methods.protectedCond(dataset,0))

def number_of_groups(dataset):
    return len(default_conditions_multiple_groups[dataset].split(' if '))

default_conditions = {'Amazon-Google': "('microsoft' in str(tuple.left_manufacturer)) or ('microsoft' in str(tuple.right_manufacturer))",
                      'Beer': "('Red' in str(tuple.left_Beer_Name)) or ('Red' in str(tuple.right_Beer_Name))",
                      'DBLP-ACM': "('female' in d.get_gender(last_author_fname_l)) or ('female' in d.get_gender(last_author_fname_r))",
                      'DBLP-GoogleScholar': "('vldb j' in str(tuple.left_venue)) or ('vldb j' in str(tuple.right_venue))",
                      'Fodors-Zagats': "('asian' == str(tuple.left_entity_type)) or ('asian' == str(tuple.right_entity_type))",
                      'iTunes-Amazon': "('Dance' in str(tuple.left_Genre)) or ('Dance' in str(tuple.right_Genre))",
                      'Walmart-Amazon': "('printers' in str(tuple.left_category)) or ('printers' in str(tuple.right_category))"}

default_conditions_multiple_groups = {'Amazon-Google': "1 if ('microsoft' in str(tuple.left_manufacturer)) or ('microsoft' in str(tuple.right_manufacturer))"
                                                       "else 2 if (('sony' in str(tuple.left_manufacturer)) or ('sony' in str(tuple.right_manufacturer)))"
                                                       "else 3 if (('apple' in str(tuple.left_manufacturer)) or ('apple' in str(tuple.right_manufacturer)))"
                                                       "else 0",
                       'Beer': "1 if ('Red' in str(tuple.left_Beer_Name)) or ('Red' in str(tuple.right_Beer_Name))"
                               "else 2 if (('Amber' in str(tuple.left_Beer_Name)) or ('Amber' in str(tuple.right_Beer_Name)))"
                               "else 0",
                       'DBLP-ACM': "1 if ('female' in str(d.get_gender(last_author_fname_l))) or ('female' in str(d.get_gender(last_author_fname_r))) else 0",
                       'DBLP-GoogleScholar': "1 if ('vldb j' in str(tuple.left_venue)) or ('vldb j' in str(tuple.right_venue))"
                                             "else 2 if (('sigmod' in str(tuple.left_venue)) or ('sigmod' in str(tuple.right_venue)))"
                                             "else 3 if (('tods' in str(tuple.left_venue)) or ('tods' in str(tuple.right_venue)))"
                                             "else 0",
                       'Fodors-Zagats': "1 if ('asian' == str(tuple.left_entity_type)) or ('asian' == str(tuple.right_entity_type)) else 0",
                       'iTunes-Amazon': "1 if ('Hip-Hop' in str(tuple.left_Genre)) or ('Hip-Hop' in str(tuple.right_Genre))"
                                        "else 2 if (('Dance' in str(tuple.left_Genre)) or ('Dance' in str(tuple.right_Genre)))"
                                        "else 3 if (('Rock' in str(tuple.left_Genre)) or ('Rock' in str(tuple.right_Genre)))"
                                        "else 0",
                       'Walmart-Amazon': "1 if (('printers' in str(tuple.left_category)) or ('printers' in str(tuple.right_category)))"
                                         "else 2 if (('laptop' in str(tuple.left_category)) or ('laptop' in str(tuple.right_category)))"
                                         "else 3 if (('cameras' in str(tuple.left_category)) or ('cameras' in str(tuple.right_category)))"
                                         "else 0"}


default_conditions_w_exp = {'Amazon-Google': "('microsoft' in str(tuple.ltable_manufacturer)) or ('microsoft' in str(tuple.rtable_manufacturer))",
                            'Beer': "('Red' in str(tuple.ltable_Beer_Name)) or ('Red' in str(tuple.rtable_Beer_Name))",
                            'DBLP-ACM': "('female' in d.get_gender(last_author_fname_l)) or ('female' in d.get_gender(last_author_fname_r))",
                            'DBLP-GoogleScholar': "('vldb j' in str(tuple.ltable_venue)) or ('vldb j' in str(tuple.rtable_venue))",
                            'Fodors-Zagats': "('asian' == str(tuple.ltable_entity_type)) or ('asian' == str(tuple.rtable_entity_type))",
                            'iTunes-Amazon': "('Dance' in str(tuple.ltable_Genre)) or ('Dance' in str(tuple.rtable_Genre))",
                            'Walmart-Amazon': "('printers' in str(tuple.ltable_category)) or ('printers' in str(tuple.rtable_category))"}

