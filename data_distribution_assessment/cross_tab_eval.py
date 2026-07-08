import pandas as pd
from tabulate import tabulate

def generate_crosstab(df, attribute_name, group_column='Group'):
    """
    Gera uma tabela cruzada para explorar a distribuição demográfica de grupos em relação a um atributo.

    Args:
        df (pd.DataFrame): DataFrame contendo os dados a serem analisados.
        attribute_name (str): Nome do atributo para análise cruzada.
        group_column (str): Nome da coluna que define os grupos (default: 'Group').

    Returns:
        pd.DataFrame: Tabela cruzada com a distribuição dos grupos em relação ao atributo.
    """
    if group_column not in df.columns or attribute_name not in df.columns:
        raise ValueError(f"'{group_column}' ou '{attribute_name}' não encontrados no DataFrame.")

    # Geração da tabela cruzada
    crosstab = pd.crosstab(df[group_column], df[attribute_name])

    print("\nTabela Cruzada:")
    print(crosstab)
    return crosstab

def run_crosstab_analysis(df, attribute_name, group_column='Group'):
    crosstab = generate_crosstab(df, attribute_name, group_column)
    print(tabulate(crosstab, headers='keys', tablefmt='grid'))
    return crosstab