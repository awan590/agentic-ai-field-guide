# Data map

## What the agent reads

Orders, returns, and the returns policy. Personal data that reaches
the model vendor is masked first. The full map comes from
[data_map.py](../../ch19/data_map.py); rerun it with
`python -m ch19.data_map` after any new table or column.

## What is kept

Traces are kept for the period in the signed data agreement, then
removed by the retention job. The data protection lead owns both.
