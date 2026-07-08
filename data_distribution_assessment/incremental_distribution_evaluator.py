from data_distribution_assessment.group_definition import *


class IncrementalEvaluator:
    def __init__(self):
        """
        Inicializa o avaliador incremental.

        Args:
            groups (list): Lista de grupos para serem avaliados.
        """
        self.attribute_distributions = {}  # Armazena distribuições independentes para cada atributo
        self.window_data = {}
        self.drift_detectors = {}

    def process_chunk(self, chunk_df, attribute_names, groups):
        """
        Processa um chunk de dados e atualiza as distribuições para cada atributo,
        fornecendo tanto a distribuição acumulada quanto a do incremento atual.

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_names (list): Lista de atributos para avaliação.

        Returns:
            dict: Contém distribuições acumuladas e do incremento atual por atributo.
        """
        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {}
        }

        for att_name in attribute_names:
            # Inicializa as contagens para o atributo, se necessário
            if att_name not in self.attribute_distributions:
                self.attribute_distributions[att_name] = {
                    "group_counts": {group: 0 for group in groups},
                    "total_count": 0
                }
                self.attribute_distributions[att_name]["group_counts"]['others'] = 0

            # Inicializa contagens para o incremento atual
            current_group_counts = {group: 0 for group in groups}
            current_group_counts['others'] = 0
            current_total_count = 0

            # Atualiza as contagens para o incremento atual e o acumulado
            for value in chunk_df[att_name].dropna():
                matched = False
                value_lower = value.lower()
                for group in groups:
                    if group in value_lower:
                        # Atualiza contagens do incremento atual
                        current_group_counts[group] += 1
                        # Atualiza contagens acumuladas
                        self.attribute_distributions[att_name]["group_counts"][group] += 1
                        matched = True
                        break
                if not matched:
                    current_group_counts['others'] += 1
                    self.attribute_distributions[att_name]["group_counts"]['others'] += 1
                current_total_count += 1

            # Atualiza o total acumulado para o atributo
            self.attribute_distributions[att_name]["total_count"] += current_total_count

            # Calcula distribuições
            if current_total_count > 0:
                current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
            else:
                current_distribution = {group: 0 for group in current_group_counts}

            cumulative_group_counts = self.attribute_distributions[att_name]["group_counts"]
            cumulative_total_count = self.attribute_distributions[att_name]["total_count"]
            cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in cumulative_group_counts.items()}

            # Armazena resultados
            results["current_increment_distribution"][att_name] = current_distribution
            results["cumulative_distribution"][att_name] = cumulative_distribution

            print(f"Cumulative Distribution {att_name}:")
            print(cumulative_distribution)
            print("--------------------------------------")

            print(f"Current Distribution {att_name}:")
            print(current_distribution)
            print("--------------------------------------")

        # print(results)
        print("======================================")

    def dynamic_process_chunk(self, chunk_df, att_name, groups):
        """
        Processa um chunk de dados e atualiza as distribuições para cada atributo,
        fornecendo tanto a distribuição acumulada quanto a do incremento atual.

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_name: atributo para avaliação.

        Returns:
            dict: Contém distribuições acumuladas e do incremento atual por atributo.
        """
        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {}
        }


        # Inicializa as contagens para o atributo, se necessário
        if att_name not in self.attribute_distributions:
            self.attribute_distributions[att_name] = {
                "group_counts": {group: 0 for group in groups},
                "total_count": 0
            }
            # self.attribute_distributions[att_name]["group_counts"]['others'] = 0

        # Inicializa contagens para o incremento atual
        current_group_counts = {group: 0 for group in groups}
        # current_group_counts['others'] = 0
        current_total_count = 0

        # Atualiza as contagens para o incremento atual e o acumulado
        for value in chunk_df[att_name].dropna():
            matched = False
            value_lower = value.lower()

            for group in groups:
                if group in value_lower:
                    # Atualiza contagens do incremento atual
                    current_group_counts[group] += 1
                    # Atualiza contagens acumuladas
                    if group not in self.attribute_distributions[att_name]["group_counts"]:
                        self.attribute_distributions[att_name]["group_counts"][group] = 1
                    else:
                        self.attribute_distributions[att_name]["group_counts"][group] += 1
                    break
            # if not matched:
            #     current_group_counts['others'] += 1
            #     self.attribute_distributions[att_name]["group_counts"]['others'] += 1
            current_total_count += 1

        # Atualiza o total acumulado para o atributo
        self.attribute_distributions[att_name]["total_count"] += current_total_count

        # Calcula distribuições
        if current_total_count > 0:
            current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
        else:
            current_distribution = {group: 0 for group in current_group_counts}

        cumulative_group_counts = self.attribute_distributions[att_name]["group_counts"]
        cumulative_total_count = self.attribute_distributions[att_name]["total_count"]
        cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in cumulative_group_counts.items()}

        # Armazena resultados
        results["current_increment_distribution"][att_name] = current_distribution
        results["cumulative_distribution"][att_name] = cumulative_distribution

        print(f"Cumulative Distribution {att_name}:")
        print(cumulative_distribution)
        print("--------------------------------------")

        print(f"Current Distribution {att_name}:")
        print(current_distribution)
        print("--------------------------------------")


        #STRATEGIES TO DEFINE GROUPS
        output = strategy_fixed_protected_groups(6, cumulative_distribution)
        print(output)
        # print(strategy_groups_by_distribution([10, 5, 1], cumulative_distribution))
        # print(strategy_adaptive_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_semantic_clustering(cumulative_distribution, 'kmeans', 3)) #não pareceu promissor, misturou muito os contextos, pois colocou software como base.
        # print(strategy_string_similarity_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_contextual_semantic_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_dynamic_distribuiton_other_group(cumulative_distribution, 4, 0.2))


        print("--------------------------------------")
        return output




    def dynamic_process_chunk_by_window(self, chunk_df, att_name, groups, window_size):
        """
        Processa um chunk de dados e atualiza as distribuições considerando uma janela deslizante.

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_names (list): Lista de atributos para avaliação.
            groups (list): Grupos predefinidos para avaliação.
            window_size (int): Tamanho da janela deslizante (em número de chunks).

        Returns:
            dict: Distribuições acumuladas e do incremento atual.
        """
        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {}
        }

        if att_name not in self.window_data:
            self.window_data[att_name] = []

        # Calcula distribuição do incremento atual
        current_group_counts = {group: 0 for group in groups}
        current_group_counts['others'] = 0
        current_total_count = 0

        for value in chunk_df[att_name].dropna():
            matched = False
            value_lower = value.lower()
            for group in groups:
                if group in value_lower:
                    current_group_counts[group] += 1
                    matched = True
                    break
            if not matched:
                current_group_counts['others'] += 1
            current_total_count += 1

        # Normaliza a distribuição do incremento atual
        if current_total_count > 0:
            current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
        else:
            current_distribution = {group: 0 for group in current_group_counts}

        # Armazena dados do incremento na janela
        self.window_data[att_name].append(current_group_counts)
        if len(self.window_data[att_name]) > window_size:
            self.window_data[att_name].pop(0)

        # Calcula distribuição acumulada com base na janela
        cumulative_group_counts = {group: 0 for group in groups}
        cumulative_group_counts['others'] = 0

        for past_counts in self.window_data[att_name]:
            for group, count in past_counts.items():
                if group not in cumulative_group_counts:
                    cumulative_group_counts[group] = count
                else:
                    cumulative_group_counts[group] += count

        cumulative_total_count = sum(cumulative_group_counts.values())
        if cumulative_total_count > 0:
            cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in cumulative_group_counts.items()}
        else:
            cumulative_distribution = {group: 0 for group in cumulative_group_counts}

        # Armazena resultados
        results["current_increment_distribution"][att_name] = current_distribution
        results["cumulative_distribution"][att_name] = cumulative_distribution

        print(f"Cumulative Distribution {att_name}:")
        print(cumulative_distribution)
        print("--------------------------------------")

        print(f"Current Distribution {att_name}:")
        print(current_distribution)
        print("--------------------------------------")


        #STRATEGIES TO DEFINE GROUPS
        # print(strategy_fixed_protected_groups(6, cumulative_distribution))
        # print(strategy_groups_by_distribution([10, 5, 1], cumulative_distribution))
        # print(strategy_adaptive_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_semantic_clustering(cumulative_distribution, 'kmeans', 3)) #não pareceu promissor, misturou muito os contextos, pois colocou software como base.
        # print(strategy_string_similarity_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_contextual_semantic_clustering(cumulative_distribution, 'kmeans', 3))
        print(strategy_dynamic_distribuiton_other_group(cumulative_distribution, 4, 0.2))


        print("--------------------------------------")

        return results




    def dynamic_process_chunk_exponential_decay(self, chunk_df, att_name, groups, decay_factor=0.9):
        """
        Processa um chunk de dados e atualiza as distribuições com um decaimento exponencial.

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_names (list): Lista de atributos para avaliação.
            groups (list): Grupos predefinidos para avaliação.
            decay_factor (float): Fator de decaimento exponencial (entre 0 e 1).

        Returns:
            dict: Distribuições acumuladas com decaimento exponencial e do incremento atual.
        """
        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {}
        }


        # Inicializa as distribuições acumuladas se necessário
        if att_name not in self.attribute_distributions:
            self.attribute_distributions[att_name] = {group: 0 for group in groups}
            self.attribute_distributions[att_name]['others'] = 0

        # Calcula a distribuição do incremento atual
        current_group_counts = {group: 0 for group in groups}
        current_group_counts['others'] = 0
        current_total_count = 0

        for value in chunk_df[att_name].dropna():
            matched = False
            value_lower = value.lower()
            for group in groups:
                if group in value_lower:
                    current_group_counts[group] += 1
                    matched = True
                    break
            if not matched:
                current_group_counts['others'] += 1
            current_total_count += 1

        # Normaliza a distribuição do incremento atual
        if current_total_count > 0:
            current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
        else:
            current_distribution = {group: 0 for group in current_group_counts}


        # Aplica o decaimento exponencial na distribuição acumulada
        for group in self.attribute_distributions[att_name]:
            self.attribute_distributions[att_name][group] *= decay_factor

        for group, count in current_group_counts.items():
            if group not in current_group_counts.items():
                self.attribute_distributions[att_name][group] = count
            else:
                self.attribute_distributions[att_name][group] += count


        # Calcula a nova distribuição acumulada
        cumulative_total_count = sum(self.attribute_distributions[att_name].values())
        if cumulative_total_count > 0:
            cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in self.attribute_distributions[att_name].items()}
        else:
            cumulative_distribution = {group: 0 for group in self.attribute_distributions[att_name]}

        # Armazena resultados
        results["current_increment_distribution"][att_name] = current_distribution
        results["cumulative_distribution"][att_name] = cumulative_distribution

        print(f"Cumulative Distribution {att_name}:")
        print(len(cumulative_distribution.keys()))
        print(cumulative_distribution)
        print("--------------------------------------")

        print(f"Current Distribution {att_name}:")
        print(current_distribution)
        print("--------------------------------------")


        #STRATEGIES TO DEFINE GROUPS
        # print(strategy_fixed_protected_groups(6, cumulative_distribution))
        # print(strategy_groups_by_distribution([10, 5, 1], cumulative_distribution))
        # print(strategy_adaptive_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_semantic_clustering(cumulative_distribution, 'kmeans', 3)) #não pareceu promissor, misturou muito os contextos, pois colocou software como base.
        # print(strategy_string_similarity_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_contextual_semantic_clustering(cumulative_distribution, 'kmeans', 3))
        print(strategy_dynamic_distribuiton_other_group(cumulative_distribution, 4, 0.2))


        print("--------------------------------------")

        return results


    def dynamic_process_chunk_exponential_decay_eviction(self, chunk_df, att_name, groups, decay_factor=0.9, near_zero_threshold=1e-3):
        """
        Processa um chunk de dados e atualiza as distribuições com um decaimento exponencial.
        Remove grupos cuja distribuição se aproxima de zero (abaixo do near_zero_threshold).

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_names (list): Lista de atributos para avaliação.
            groups (list): Grupos predefinidos para avaliação.
            decay_factor (float): Fator de decaimento exponencial (entre 0 e 1).
            near_zero_threshold (float): Valor limite abaixo do qual grupos serão removidos.

        Returns:
            dict: Distribuições acumuladas com decaimento exponencial e do incremento atual.
        """
        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {}
        }

        # Inicializa as distribuições acumuladas se necessário
        if att_name not in self.attribute_distributions:
            self.attribute_distributions[att_name] = {group: 0 for group in groups}
            self.attribute_distributions[att_name]['others'] = 0

        # Calcula a distribuição do incremento atual
        current_group_counts = {group: 0 for group in groups}
        current_group_counts['others'] = 0
        current_total_count = 0

        for value in chunk_df[att_name].dropna():
            matched = False
            value_lower = value.lower()
            for group in groups:
                if group in value_lower:
                    current_group_counts[group] += 1
                    matched = True
                    break
            if not matched:
                current_group_counts['others'] += 1
            current_total_count += 1

        # Normaliza a distribuição do incremento atual
        if current_total_count > 0:
            current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
        else:
            current_distribution = {group: 0 for group in current_group_counts}

        # Aplica o decaimento exponencial e remove grupos próximos de zero
        for group in list(self.attribute_distributions[att_name].keys()):
            if group in current_group_counts and current_group_counts[group] > 0:
                self.attribute_distributions[att_name][group] += current_group_counts[group]
            else:
                self.attribute_distributions[att_name][group] *= decay_factor

            # Remove grupos cuja distribuição se aproxima de zero
            if abs(self.attribute_distributions[att_name][group]) < near_zero_threshold:
                print("Eviction of " + group)
                del self.attribute_distributions[att_name][group]

        # Calcula a nova distribuição acumulada
        cumulative_total_count = sum(self.attribute_distributions[att_name].values())
        if cumulative_total_count > 0:
            cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in self.attribute_distributions[att_name].items()}
        else:
            cumulative_distribution = {group: 0 for group in self.attribute_distributions[att_name]}

        # Armazena resultados
        results["current_increment_distribution"][att_name] = current_distribution
        results["cumulative_distribution"][att_name] = cumulative_distribution

        print(f"Cumulative Distribution {att_name}:")
        print(len(cumulative_distribution.keys()))
        print(cumulative_distribution)
        print("--------------------------------------")

        print(f"Current Distribution {att_name}:")
        print(current_distribution)
        print("--------------------------------------")


        #STRATEGIES TO DEFINE GROUPS
        # print(strategy_fixed_protected_groups(6, cumulative_distribution))
        # print(strategy_groups_by_distribution([10, 5, 1], cumulative_distribution))
        # print(strategy_adaptive_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_semantic_clustering(cumulative_distribution, 'kmeans', 3)) #não pareceu promissor, misturou muito os contextos, pois colocou software como base.
        # print(strategy_string_similarity_clustering(cumulative_distribution, 'kmeans', 3))
        # print(strategy_contextual_semantic_clustering(cumulative_distribution, 'kmeans', 3))
        print(strategy_dynamic_distribuiton_other_group(cumulative_distribution, 4, 0.2))


        print("--------------------------------------")

        return results



    def dynamic_process_chunk_drift_detection(self, chunk_df, att_name, groups, drift_detector_class='ADWIN'):
        """
        Processa um chunk de dados utilizando detecção de drift para ajustar dinamicamente a distribuição.
        Se um drift for detectado, descarta os dados antigos e ajusta os grupos para refletir a nova distribuição.

        Args:
            chunk_df (pd.DataFrame): Chunk de pares de entidades.
            attribute_names (list): Lista de atributos para avaliação.
            groups (list): Grupos predefinidos para avaliação.
            drift_detector_class: Classe de detecção de drift (ex.: ADWIN, DDM).
            warning_threshold (float): Limite de alerta para iniciar ajustes em caso de drift detectado.

        Returns:
            dict: Distribuições ajustadas dinamicamente com base na detecção de drift.
        """
        from river.drift import ADWIN, DDM

        results = {
            "cumulative_distribution": {},
            "current_increment_distribution": {},
            "drift_detected": {}
        }

        if drift_detector_class == 'DDM':
            print("DDM selected.")
            drift_detector = DDM
        else:
            print("ADWIN selected.")
            drift_detector = ADWIN

        if att_name not in self.drift_detectors:
            self.drift_detectors[att_name] = {
                group: drift_detector for group in groups + ["others"]
            }

        if att_name not in self.attribute_distributions:
            self.attribute_distributions[att_name] = {group: 0 for group in groups}
            self.attribute_distributions[att_name]['others'] = 0

        # Calcula a distribuição do incremento atual
        current_group_counts = {group: 0 for group in groups}
        current_group_counts['others'] = 0
        current_total_count = 0

        for value in chunk_df[att_name].dropna():
            matched = False
            value_lower = value.lower()
            for group in groups:
                if group in value_lower:
                    current_group_counts[group] += 1
                    matched = True
                    break
            if not matched:
                current_group_counts['others'] += 1
            current_total_count += 1

        if current_total_count > 0:
            current_distribution = {group: (count / current_total_count) * 100 for group, count in current_group_counts.items()}
        else:
            current_distribution = {group: 0 for group in current_group_counts}

        drift_detected = {}
        for group, detector in self.drift_detectors[att_name].items():
            value = current_distribution.get(group, 0)
            detector.update(value)
            drift_detected[group] = detector.change_detected

        # Verifica se há drift em qualquer grupo
        if any(drift_detected.values()):
            # Se drift for detectado, descarta os dados antigos e redefine a distribuição
            self.attribute_distributions[att_name] = current_distribution
        else:
            # Atualiza a distribuição acumulada normalmente
            for group, value in current_distribution.items():
                self.attribute_distributions[att_name][group] = (
                        self.attribute_distributions[att_name].get(group, 0) + value
                )

        # Calcula a nova distribuição acumulada
        cumulative_total_count = sum(self.attribute_distributions[att_name].values())
        if cumulative_total_count > 0:
            cumulative_distribution = {group: (count / cumulative_total_count) * 100 for group, count in self.attribute_distributions[att_name].items()}
        else:
            cumulative_distribution = {group: 0 for group in self.attribute_distributions[att_name]}

        results["current_increment_distribution"][att_name] = current_distribution
        results["cumulative_distribution"][att_name] = cumulative_distribution
        results["drift_detected"][att_name] = drift_detected

        return results


