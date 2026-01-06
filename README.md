# Proyectos2


# first 2 columns of df2
first_cols = df2.iloc[:, :2]

# remaining columns
df1_rest = df1
df2_rest = df2.iloc[:, 2:]

# intercalate columns
intercalated_cols = []
for i in range(df1_rest.shape[1]):
    intercalated_cols.append(df1_rest.iloc[:, i])
    intercalated_cols.append(df2_rest.iloc[:, i])

# build final dataframe
df_final = pd.concat([first_cols] + intercalated_cols, axis=1)

# generate CSV string
csv_string = df_final.to_csv(index=False)

# Convert to CSV string
csv_string = interleaved_df.to_csv(index=False)

print(csv_string)

