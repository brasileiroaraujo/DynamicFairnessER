import time
import pandas as pd

from data_distribution_assessment.distribution_metrics import evaluate_distribution_metrics
from data_distribution_assessment.group_definition import extract_group_keys
from data_distribution_assessment.incremental_distribution_evaluator import IncrementalEvaluator


def open_csv(path):
    return pd.read_csv(path, header=None, sep='\n')


def run_evaluator_defined_groups(list_of_pairs, attribute_names, groups):
    df = convert_to_dataframe(list_of_pairs)

    for att_name in attribute_names:
        calculate_distribution_by_groups(df, att_name, groups)
        print("--------------------------------------")
    print("======================================")

def run_evaluator(list_of_pairs, attribute_names):
    df = convert_to_dataframe(list_of_pairs)

    # # for column in df.columns:
    # #     print(column)
    # print(df.columns)

    for att_name in attribute_names:
        calculate_distribution(df, att_name)
        calculate_unique_keys(df, att_name)
        print("--------------------------------------")

def calculate_distribution(df, attribute_name):
    print(attribute_name)
    counts = df[attribute_name].value_counts()

    # Calculate the percentage distribution
    percentage_distribution = counts / counts.sum() * 100

    print(percentage_distribution)

def calculate_unique_keys(df,attribute_name):
    unique_keys = df[attribute_name].nunique()
    print(unique_keys)

def calculate_distribution_by_groups(df, attribute_name, groups):
    """
    Calculates the distribution of groups based on the presence of group keywords
    in the attribute values.

    Args:
        df (pd.DataFrame): The input DataFrame containing attribute columns.
        attribute_name (str): The column name to analyze.
        groups (list): List of group keywords to match against.

    Returns:
        None
    """
    print(f"Evaluating CURRENT distribution for attribute: {attribute_name}")

    # Initialize a dictionary to store counts for each group
    group_counts = {group: 0 for group in groups}
    group_counts['others'] = 0  # For values that don't match any group

    # Iterate through the DataFrame to evaluate each value in the attribute
    for value in df[attribute_name].dropna():  # Exclude NaN values
        matched = False
        value_lower = value.lower()  # Ensure case-insensitive matching
        for group in groups:
            if group in value_lower:
                group_counts[group] += 1
                matched = True
                break
        if not matched:
            group_counts['others'] += 1

    # Calculate total occurrences for percentage calculation
    total_occurrences = sum(group_counts.values())

    # Calculate percentage distribution
    percentage_distribution = {group: (count / total_occurrences) * 100
                               for group, count in group_counts.items()}

    # Display results
    print("Distribution Counts:")
    print(group_counts)
    print("Percentage Distribution:")
    print(percentage_distribution)

def add_row(att_list, att_value_map, side):
    for att_value in att_list:
        if len(att_value) == 2:
            att_value[0] = side + att_value[0].strip()
            if att_value[0].strip() in att_value_map.keys():
                att_value_map[att_value[0].strip()].append(att_value[1].strip())
            else:
                att_value_map[att_value[0].strip()] = [att_value[1].strip()]

def convert_to_dataframe(list_of_pairs):
    att_value_map = {}

    for row in list_of_pairs.to_numpy():
        left = row[0].split('\t')[0]
        right = row[0].split('\t')[1]

        att_l = [att_value.split('VAL') for att_value in left.split('COL')]
        add_row(att_l, att_value_map, 'left_')

        att_r = [att_value.split('VAL') for att_value in right.split('COL')]
        add_row(att_r, att_value_map, 'right_')

    return pd.DataFrame.from_dict(att_value_map)





#main to test
task = 'Amazon-Google'#'DBLP-GoogleScholar'
sensitive_attributes = ['left_manufacturer', 'right_manufacturer']#['left_venue', 'right_venue']
BASE_PATH = "../data/er_magellan/Structured/"
pairs_to_compare = open_csv(BASE_PATH + task + '/test.txt')
# run_evaluator(pairs_to_compare, sensitive_attributes)


init = 0
n_batches = 1000
window = n_batches - init
pair_size = len(pairs_to_compare.index) - 1

list_of_pairs = []
#groups = ['microsoft', 'sony', 'apple', 'adobe']
evaluator = IncrementalEvaluator()

while ((not pairs_to_compare.empty) and (init < pair_size)):#for i in range(0,len(preds.index)):
    lines = pairs_to_compare.loc[init:min(n_batches, pair_size)]

    for row in lines.to_numpy():
        triple = row[0].split("\t")
        data = [triple[0], triple[1]]#.loc[i].to_json()
        list_of_pairs.append(data)

    init = n_batches + 1
    n_batches = init + (window) #if (n_batches + (window) < len(source.index)) else dataset_size
    print("pairs size: " + str(len(lines.index)))

    groups = extract_group_keys(convert_to_dataframe(lines), sensitive_attributes[0])

    # calculate_unique_keys(convert_to_dataframe(lines), 'left_manufacturer')
    # calculate_distribution(convert_to_dataframe(lines), 'left_manufacturer')

    #Define group menager strategy
    evaluator.dynamic_process_chunk(convert_to_dataframe(lines), sensitive_attributes[0], groups)
    # evaluator.dynamic_process_chunk_by_window(convert_to_dataframe(lines), sensitive_attributes[0], groups, 3)
    # evaluator.dynamic_process_chunk_exponential_decay_eviction(convert_to_dataframe(lines), sensitive_attributes[0], groups, 0.9, 0.01)
    # evaluator.dynamic_process_chunk_drift_detection(convert_to_dataframe(lines), sensitive_attributes[0], groups,"ADWIN")



    # run_evaluator_defined_groups(pairs_to_compare, sensitive_attributes, groups)
    # evaluator.get_current_distributions(convert_to_dataframe(lines), sensitive_attributes)
    time.sleep(3)

# run_crosstab_analysis(convert_to_dataframe(pairs_to_compare), attribute_name='right_manufacturer', group_column='left_manufacturer')
# evaluate_distribution_metrics(convert_to_dataframe(pairs_to_compare), sensitive_attributes)





