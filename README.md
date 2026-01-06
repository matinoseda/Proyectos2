# Proyectos2


import pandas as pd

# Example dataframes
df1 = pd.DataFrame([[1, 2, 3],
                    [4, 5, 6],
                    [7, 8, 9]])

df2 = pd.DataFrame([[10, 20, 30],
                    [40, 50, 60],
                    [70, 80, 90]])

# Interleave columns
interleaved_df = pd.concat(
    [df1.iloc[:, i].rename(f"df1_{i}") for i in range(df1.shape[1])] +
    [df2.iloc[:, i].rename(f"df2_{i}") for i in range(df2.shape[1])],
    axis=1
)

# Reorder columns to interleave properly
cols = []
for i in range(df1.shape[1]):
    cols.extend([f"df1_{i}", f"df2_{i}"])

interleaved_df = interleaved_df[cols]

# Convert to CSV string
csv_string = interleaved_df.to_csv(index=False)

print(csv_string)

