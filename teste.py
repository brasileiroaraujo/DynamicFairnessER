# # l = ['', ' id VAL 0 ', ' Beer_Name VAL TrÃ ¶ egs Nugget Nectar ', ' Brew_Factory_Name VAL TrÃ ¶ egs Brewing Company ', ' Style VAL American Amber / Red Ale ', ' ABV VAL 7.50 % ']
# #
# # l = 'COL' + 'COL'.join(l[2:])
# #
# # print(l)
#
# input_file = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/Amazon-Google/"
# output_file = "D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/Amazon-Google/test_utf.txt"
#
# files = ["test.txt"]#["test.txt", "train.txt", "valid.txt"]
#
# # for i in files:
# #     with open(input_file+i, 'r', encoding="latin-1") as input:
# #         with open(output_file, 'a', encoding="utf8") as output:
# #             lines = input.readlines()
# #             for line in lines:
# #                 output.write(line);
#
#
# # with open("D:/IntelliJ_Workspace/fairER/data/er_magellan/Structured/Amazon-Google/all_data.txt", encoding="utf8") as file:
# #     for line in file:
# #         triple = line.split("\t")
# #         if int(triple[2].strip()) == 1:
# #             print(line)
# a = []
# if (not a):
#     print('vazio')



def explanation_score(s: float, p: float, alpha_factor: float = 1) -> float:
    """
    Calcula o Explanation Score (ES) baseado nos parâmetros s e p.

    Fórmula:
        ES = s + p * abs(s) * (1 - abs(s))

    Onde:
        s ∈ [-1, 1]  → score principal
        p ∈ [-1, 1]  → potential (atua como atenuador/potencializador)

    Retorna:
        ES ∈ [-1, 1] aproximadamente
    """
    ES = s + alpha_factor * p * abs(s) * (1 - abs(s))
    # Garante que o valor fique limitado ao intervalo [-1, 1]
    ES = max(min(ES, 1.0), -1.0)
    return ES


# 🔍 Exemplos de teste:
casos = [
    (-0.40, -0.60),
    (-0.40, +0.50),
    (+0.50, +0.60),
    (+0.50, -0.60)
]

for s, p in casos:
    print(f"s={s:+.2f}, p={p:+.2f} → ES={explanation_score(s, p):+.3f}")