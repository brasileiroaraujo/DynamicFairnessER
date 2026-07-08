def get_accuracy(clusters, preds):
    correct_results = 0
    num_results = len(clusters) * 1.0

    for cluster in clusters:
        left_id = cluster[0]
        right_id = cluster[1]
        # label = preds['label'][(preds['left_id'] == left_id) & (preds['right_id'] == right_id)]
        id_location = preds['left_Beer_Name']+'_'+preds['right_Beer_Name'] == str(left_id)+'_'+str(right_id)
        score = preds['match_score'][id_location]
        label = preds['label'][id_location]
        print(left_id, right_id, label.all(), score.values[0])
        if label.all() == 1:
            correct_results += 1

    accuracy = correct_results / num_results
    # print("accuracy: ", accuracy)
    return accuracy