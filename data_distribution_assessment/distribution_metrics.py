import numpy as np
from scipy.stats import entropy

def calculate_entropy(distribution):
    """
    Calcula a entropia da distribuição.

    Args:
        distribution (list ou np.array): Frequências ou proporções da distribuição.

    Returns:
        float: Entropia da distribuição.
    """
    distribution = np.array(distribution) / np.sum(distribution)  # Normaliza as frequências para proporções
    return entropy(distribution)


def calculate_gini(distribution):
    """
    Calcula o coeficiente de Gini da distribuição.

    Args:
        distribution (list ou np.array): Frequências ou proporções da distribuição.

    Returns:
        float: Coeficiente de Gini.
    """
    sorted_distribution = np.sort(distribution)  # Ordena a distribuição
    n = len(distribution)
    cumulative_sum = np.cumsum(sorted_distribution, dtype=float)
    gini = (n + 1 - 2 * np.sum(cumulative_sum) / cumulative_sum[-1]) / n
    return gini


def evaluate_distribution_metrics(df, sensitive_attributes):
    """
    Avalia métricas de distribuição (Entropia e Gini) para grupos protegidos.

    Args:
        list_of_pairs (pd.DataFrame): Pares de entidades a serem analisados.
        group_column (str): Nome da coluna que define os grupos (default: 'Group').

    Returns:
        dict: Resultados das métricas (Entropia e Gini).
    """
    for sensitive_attribute in sensitive_attributes:
        print(f"Evaluating distribution for attribute: {sensitive_attribute}")
        # Calcula a distribuição
        group_counts = df[sensitive_attribute].value_counts()

        # Calcula as métricas
        entropy_value = calculate_entropy(group_counts)
        gini_value = calculate_gini(group_counts)

        # Calcula a entropia máxima
        num_groups = len(group_counts)
        max_entropy = np.log(num_groups)  # Usando base natural

        # Normaliza a entropia
        normalized_entropy = entropy_value / max_entropy if max_entropy > 0 else 0

        #Remember: The Gini measures inequality in the distribution of values. Entropy measures uncertainty or disorder in the distribution.
        #Then, we can have different values. A high Gini: extreme inequality, as most of the probability is concentrated in one event.
        #A low entropy: low uncertainty because one event completely dominates the distribution.
        print(f"Entropy of the Distribution: {entropy_value:.4f}")
        print(f"Maximum Possible Entropy: {max_entropy:.4f}")
        print(f"Normalized Entropy [0,1]: {normalized_entropy:.4f}") # Close to 0 indicates low uncertainty and low diversity, while close to 1 represents high uncertainty or greater diversity.
        print(f"Gini Coefficient [0,1]: {gini_value:.4f}") # Values close to 0 indicate equality, while values closer to 1 indicate greater inequality.
        print("--------------------------------------")
