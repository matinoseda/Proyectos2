result_cols = [df2.iloc[:, :2]]

# Intercalate df1 and middle columns of df2
for i in range(df1.shape[1]):
    result_cols.append(df1.iloc[:, [i]])
    result_cols.append(df2.iloc[:, [i + 2]])

# Last column of df2
result_cols.append(df2.iloc[:, [-1]])

# Concatenate all parts
result_df = pd.concat(result_cols, axis=1)

# Convert to CSV string
csv_string = result_df.to_csv(index=False)
