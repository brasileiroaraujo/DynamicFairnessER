from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import pairwise_distances
import numpy as np
import Levenshtein
from sklearn.feature_extraction.text import CountVectorizer


def extract_group_keys(df, attribute_name):
    print("Getting unique values for " + attribute_name)
    group_keys = df[attribute_name].drop_duplicates().tolist()
    return group_keys


def strategy_fixed_protected_groups(num_groups, cumulative_distribution):
    """
    Groups the data into `num_groups` largest distributions, combining the rest into an "others" group.

    :param num_groups: Number of groups to retain based on the largest distributions.
    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :return: A dictionary with `num_groups` largest distributions and an "others" group.
    """
    if num_groups <= 0:
        raise ValueError("Number of groups must be greater than zero.")

    # Sort the cumulative distribution by values in descending order
    sorted_distribution = sorted(cumulative_distribution.items(), key=lambda x: x[1], reverse=True)

    # Select the top `num_groups`
    top_groups = sorted_distribution[:num_groups]

    # Combine the rest into "others"
    other_groups = sorted_distribution[num_groups:]
    others_total = sum(value for _, value in other_groups)

    # Prepare the resulting grouped distribution
    grouped_distribution = {group: value for group, value in top_groups}
    if others_total > 0:
        grouped_distribution["others"] = others_total

    return grouped_distribution

def strategy_groups_by_distribution(frequency_thresholds, cumulative_distribution):
    """
    Groups the data into variable-sized groups based on frequency thresholds.

    :param frequency_thresholds: List of thresholds defining group ranges (in descending order).
    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :return: A dictionary with groups defined by thresholds and an "others" group.
    """
    if not frequency_thresholds:
        raise ValueError("Frequency thresholds must be provided.")

    # Sort the cumulative distribution by values in descending order
    sorted_distribution = sorted(cumulative_distribution.items(), key=lambda x: x[1], reverse=True)

    grouped_distribution = {}
    others_total = 0

    for threshold in frequency_thresholds:
        group_name = f"above_{threshold}"
        group_total = 0

        # Collect items above the current threshold
        for key, value in sorted_distribution[:]:
            if value > threshold:
                group_total += value
                sorted_distribution.remove((key, value))

        if group_total > 0:
            grouped_distribution[group_name] = group_total

    # Remaining items go into "others"
    others_total = sum(value for _, value in sorted_distribution)
    if others_total > 0:
        grouped_distribution["others"] = others_total

    return grouped_distribution

def strategy_dynamic_distribuiton_other_group(cumulative_distribution, num_main_groups=3, others_threshold=0.2):
    """
    Dynamically adjusts the size of the "others" group by redistributing low-frequency values to main groups.

    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :param num_main_groups: Number of main groups to retain.
    :param others_threshold: Proportion threshold for the "others" group before redistributing values.
    :return: A dictionary with main groups and a dynamically adjusted "others" group.
    """
    # Sort the cumulative distribution by values in descending order
    sorted_distribution = sorted(cumulative_distribution.items(), key=lambda x: x[1], reverse=True)

    # Select the top `num_main_groups` groups
    main_groups = sorted_distribution[:num_main_groups]
    remaining_items = sorted_distribution[num_main_groups:]

    # Calculate total values for main groups and others
    total_main = sum(value for _, value in main_groups)
    total_others = sum(value for _, value in remaining_items)
    total_distribution = total_main + total_others

    grouped_distribution = {group: value for group, value in main_groups}

    # Monitor the proportion of "others" group
    if total_others / total_distribution > others_threshold:
        # Redistribute the most frequent values from "others" to main groups
        redistributable_items = sorted(remaining_items, key=lambda x: x[1], reverse=True)
        for item, value in redistributable_items:
            if total_others / total_distribution <= others_threshold:
                break

            # Add the item to the main groups if below the threshold
            main_group_name = f"{item}"
            grouped_distribution[main_group_name] = value

            # Adjust totals
            total_main += value
            total_others -= value

        # Update remaining items for "others"
        remaining_items = [(item, value) for item, value in remaining_items if item not in grouped_distribution]

    # Update the "others" group with the remaining items
    grouped_distribution['others'] = sum(value for _, value in remaining_items)

    return grouped_distribution

def strategy_adaptive_clustering(cumulative_distribution, clustering_method='kmeans', n_clusters=3, **kwargs):
    """
    Groups the data using clustering methods such as k-means or DBSCAN, with an additional cluster for "others".

    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :param clustering_method: Clustering method to use ('kmeans' or 'dbscan').
    :param n_clusters: Number of clusters for k-means (ignored for DBSCAN).
    :param kwargs: Additional arguments for the clustering algorithm.
    :return: A dictionary with adaptive clusters, their items, and an "others" group.
    """

    # Convert cumulative distribution to a list of values for clustering
    items = list(cumulative_distribution.keys())
    values = np.array(list(cumulative_distribution.values())).reshape(-1, 1)

    if clustering_method == 'kmeans':
        # Apply k-means clustering
        model = KMeans(n_clusters=n_clusters, **kwargs)
    elif clustering_method == 'dbscan':
        # Apply DBSCAN clustering
        model = DBSCAN(**kwargs)
    else:
        raise ValueError("Unsupported clustering method. Choose 'kmeans' or 'dbscan'.")

    # Fit the model and get cluster labels
    labels = model.fit_predict(values)

    grouped_distribution = {}
    for label in set(labels):
        if label == -1:  # Noise or unclustered points
            group_name = "others"
        else:
            group_name = f"cluster_{label}"

        # Gather items and their cumulative values for the cluster
        cluster_items = [(items[i], values[i][0]) for i in range(len(labels)) if labels[i] == label]

        grouped_distribution[group_name] = {
            "total": sum(value for _, value in cluster_items),
            "items": {item: value for item, value in cluster_items}
        }

    return grouped_distribution


def strategy_semantic_clustering(cumulative_distribution, clustering_method='kmeans', n_clusters=3, **kwargs):
    """
    Groups the data using clustering methods such as k-means or DBSCAN, based on semantic similarity of keys.

    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :param clustering_method: Clustering method to use ('kmeans' or 'dbscan').
    :param n_clusters: Number of clusters for k-means (ignored for DBSCAN).
    :param kwargs: Additional arguments for the clustering algorithm.
    :return: A dictionary with semantic clusters, their items, and an "others" group.
    """

    # Extract keys and values
    items = list(cumulative_distribution.keys())
    values = np.array(list(cumulative_distribution.values()))

    # Compute semantic similarity using TF-IDF
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(items)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    if clustering_method == 'kmeans':
        # Apply k-means clustering on similarity matrix
        model = KMeans(n_clusters=n_clusters, **kwargs)
    elif clustering_method == 'dbscan':
        # Apply DBSCAN clustering on similarity matrix
        model = DBSCAN(metric='precomputed', **kwargs)
    else:
        raise ValueError("Unsupported clustering method. Choose 'kmeans' or 'dbscan'.")

    # Fit the model and get cluster labels
    labels = model.fit_predict(similarity_matrix if clustering_method == 'dbscan' else tfidf_matrix)

    grouped_distribution = {}
    for label in set(labels):
        if label == -1:  # Noise or unclustered points
            group_name = "others"
        else:
            group_name = f"cluster_{label}"

        # Gather items and their cumulative values for the cluster
        cluster_items = [(items[i], values[i]) for i in range(len(labels)) if labels[i] == label]

        grouped_distribution[group_name] = {
            "total": sum(value for _, value in cluster_items),
            "items": {item: value for item, value in cluster_items}
        }

    return grouped_distribution


def strategy_string_similarity_clustering(cumulative_distribution, clustering_method='kmeans', n_clusters=3, similarity_metric='levenshtein', **kwargs):
    """
    Groups the data using clustering methods such as k-means or DBSCAN, based on string similarity of keys.

    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :param clustering_method: Clustering method to use ('kmeans' or 'dbscan').
    :param n_clusters: Number of clusters for k-means (ignored for DBSCAN).
    :param similarity_metric: Metric to use for string similarity ('jaccard' or 'levenshtein').
    :param kwargs: Additional arguments for the clustering algorithm.
    :return: A dictionary with string similarity clusters, their items, and an "others" group.
    """
    # Extract keys and values
    items = list(cumulative_distribution.keys())
    values = np.array(list(cumulative_distribution.values()))

    # Compute string similarity matrix
    if similarity_metric == 'levenshtein':
        similarity_matrix = np.array([
            [Levenshtein.ratio(a, b) for b in items] for a in items
        ])
    elif similarity_metric == 'jaccard':
        vectorizer = CountVectorizer(analyzer='char', ngram_range=(1, 2))
        char_vectors = vectorizer.fit_transform(items)
        similarity_matrix = 1 - pairwise_distances(char_vectors, metric='jaccard')
    else:
        raise ValueError("Unsupported similarity metric. Choose 'levenshtein' or 'jaccard'.")

    if clustering_method == 'kmeans':
        # Apply k-means clustering on similarity matrix
        model = KMeans(n_clusters=n_clusters, **kwargs)
    elif clustering_method == 'dbscan':
        # Apply DBSCAN clustering on similarity matrix
        model = DBSCAN(metric='precomputed', **kwargs)
    else:
        raise ValueError("Unsupported clustering method. Choose 'kmeans' or 'dbscan'.")

    # Fit the model and get cluster labels
    labels = model.fit_predict(similarity_matrix)

    grouped_distribution = {}
    for label in set(labels):
        if label == -1:  # Noise or unclustered points
            group_name = "others"
        else:
            group_name = f"cluster_{label}"

        # Gather items and their cumulative values for the cluster
        cluster_items = [(items[i], values[i]) for i in range(len(labels)) if labels[i] == label]

        grouped_distribution[group_name] = {
            "total": sum(value for _, value in cluster_items),
            "items": {item: value for item, value in cluster_items}
        }

    return grouped_distribution


def strategy_contextual_semantic_clustering(cumulative_distribution, clustering_method='kmeans', n_clusters=3, **kwargs):
    """
    Groups the data using clustering methods such as k-means or DBSCAN, based on contextual semantic similarity of keys.

    :param cumulative_distribution: A dictionary with items and their cumulative distribution values.
    :param clustering_method: Clustering method to use ('kmeans' or 'dbscan').
    :param n_clusters: Number of clusters for k-means (ignored for DBSCAN).
    :param kwargs: Additional arguments for the clustering algorithm.
    :return: A dictionary with contextual semantic clusters, their items, and an "others" group.
    """

    # Load a pre-trained sentence transformer model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Extract keys and values
    items = list(cumulative_distribution.keys())
    values = np.array(list(cumulative_distribution.values()))

    # Compute semantic embeddings for each item
    embeddings = model.encode(items)

    if clustering_method == 'kmeans':
        # Apply k-means clustering on embeddings
        model = KMeans(n_clusters=n_clusters, **kwargs)
    elif clustering_method == 'dbscan':
        # Apply DBSCAN clustering on embeddings
        model = DBSCAN(metric='euclidean', **kwargs)
    else:
        raise ValueError("Unsupported clustering method. Choose 'kmeans' or 'dbscan'.")

    # Fit the model and get cluster labels
    labels = model.fit_predict(embeddings)

    grouped_distribution = {}
    for label in set(labels):
        if label == -1:  # Noise or unclustered points
            group_name = "others"
        else:
            group_name = f"cluster_{label}"

        # Gather items and their cumulative values for the cluster
        cluster_items = [(items[i], values[i]) for i in range(len(labels)) if labels[i] == label]

        grouped_distribution[group_name] = {
            "total": sum(value for _, value in cluster_items),
            "items": {item: value for item, value in cluster_items}
        }

    return grouped_distribution

