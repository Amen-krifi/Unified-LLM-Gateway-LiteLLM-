import pandas as pd

df = pd.read_csv("benchmark/questions.csv")
print("Rows:", len(df))
print(df["category"].value_counts())