# Data

Source dataset files used by the pipeline.

```
data/
├── EdNet-KT4/       # Per-student interaction CSV files (e.g. u1.csv, u100.csv, ...)
└── EdNet-Contents/
    └── contents/    # Question and lecture metadata (questions.csv, lectures.csv)
```

## Dataset: EdNet-KT4

| Property | Value |
|---|---|
| **Source** | [github.com/riiid/ednet](https://github.com/riiid/ednet) |
| **Licence** | CC BY-NC 4.0 |
| **Volume** | >100 million time-stamped events, ~780 000 students, ~297 000 CSV files |
| **Format** | One CSV file per student (e.g. `u12345.csv`) |
| **Key columns** | `timestamp` (epoch ms), `solving_id`, `question_id`, `user_answer`, `elapsed_time` |

A small sample is included in the repository. For the full dataset, download from the EdNet GitHub page and place files here.

## How It Is Used

The **ingestion microservice** reads files from this directory, validates them, converts to Parquet, and writes to the HDFS raw zone. This directory is mounted read-only into the ingestion container.
