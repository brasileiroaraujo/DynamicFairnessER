import lemon
import pandas as pd

dataset = lemon.utils.datasets.deepmatcher.textual_abt_buy()

matcher = lemon.utils.matchers.MagellanMatcher()

matcher.fit(
    dataset.train.records.a,
    dataset.train.records.b,
    dataset.train.record_id_pairs,
    dataset.train.labels,
)

output_eval = matcher.evaluate(
    dataset.test.records.a,
    dataset.test.records.b,
    dataset.test.record_id_pairs,
    dataset.test.labels,
)


print(output_eval)


records_a = dataset.records.a.convert_dtypes()
records_b = dataset.records.a.convert_dtypes()
records_a = (
    dataset.test.record_id_pairs[["a.rid"]]
        .merge(records_a, how="left", left_on="a.rid", right_index=True)
        .rename(columns={"a.rid": "rid"})
)
records_b = (
    dataset.test.record_id_pairs[["b.rid"]]
        .merge(records_b, how="left", left_on="b.rid", right_index=True)
        .rename(columns={"b.rid": "rid"})
)
records_a = records_a.drop(columns="rid")
records_b = records_b.drop(columns="rid")
record_pairs = pd.concat((records_a, records_b), axis=1, keys=["a", "b"], names=["source", "attribute"])


record_pair = record_pairs.iloc[0:1]


# print("PROBA")
# print(matcher.predict_proba(record_a=record_pair["a"],
#                             records_b=record_pair["b"],
#                             record_id_pairs=pd.DataFrame(#AQUI TEM QUE TER DE ALGUMA FORMA O PID
#                                 {"pid": [0], "a.rid": [record_pair.index[0]], "b.rid": [record_pair.index[0]]})))
# print("------------")

exp = lemon.explain(
    dataset.records.a,
    dataset.records.b,
    dataset.test.record_id_pairs.iloc[0:2],
    matcher.predict_proba,
    granularity="attributes"
    # explain_attrs=True
    # dual_explanation=False
    # attribution_method="shap",
    # estimate_potential=False
)


print("PAIRS:")
print(dataset.test.record_id_pairs.iloc[0:2])
print("----------------")

#for more than one record to evaluate
for item in exp.values():
    print(item.string_representation)
    print("----------------")
    print(item.attributions)
    # print("----------------")
    # print(item.metadata)
    # print("----------------")
    # print(item.record_pair)
    # print("----------------")
    # print(item.dual)
    # print("----------------")
    # print(item.prediction_score)
    print("----------------")

    print(item.as_html())
    ax, plt = item.plot_treats("both")
    plt.show()



#for only one record to evaluate
# ax, plt = exp.plot_treats("both")
# plt.show()




# exp.save("exp.json")
# exp = lemon.MatchingAttributionExplanation.load("exp.json")
#
# # lemon.MatchingAttributionExplanation.plot(exp)
# ax, plt = exp.plot_treats("both")
# plt.show()