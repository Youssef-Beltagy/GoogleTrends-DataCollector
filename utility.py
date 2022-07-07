import pandas as pd


df = pd.read_csv("data.csv", index_col=0)

output = None
for symbol in df.columns:
    exchange, ticker = symbol.split(":")

    df2 = pd.DataFrame({
        "exchange":exchange,
        "ticker":ticker,
        "google trends score":df[symbol]
    })

    df2.reset_index(inplace=True)

    output = pd.concat([output, df2], axis=0, ignore_index=True)

print(f"output shape: {output.shape}")
if output is not None:
    output.to_csv("formatted.csv", index=False)
