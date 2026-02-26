# Dataset Setup — EdNet

> How to download and place the EdNet dataset for this project.

---

## About the Dataset

This system uses the **EdNet** dataset, published by Riiid! (Santa Labs). It is a large-scale student interaction dataset collected from a Korean AI tutoring platform.

| Dataset | Size | Description |
|---|---|---|
| **EdNet-KT4** | >100M rows | Time-stamped student interaction events |
| **EdNet-Contents** | ~13K rows | Question and lecture content metadata |

**Citation:**
> Choi, Y., et al. (2020). *EdNet: A Large-Scale Hierarchical Dataset in Education.* Springer, 2020.
> https://arxiv.org/abs/1912.03072

---

## Download

### 1. Get the dataset

Visit the official EdNet repository:

**https://github.com/riiid/ednet**

Download from the link provided there. You will need:
- `KT4.zip` — the full KT4 interaction dataset
- `contents.zip` — question and lecture content files

> **Note:** The full dataset is large (~4 GB compressed). A small sample subset is sufficient for demonstration purposes.

---

## Folder Structure

Place the extracted files in this exact structure inside the project root:

```
DataEngineeringProjectIU/
└── data/
    ├── EdNet-KT4/
    │   ├── u1.csv
    │   ├── u2.csv
    │   ├── u3.csv
    │   └── ...                  ← one CSV per student (KT4 format)
    │
    └── EdNet-Contents/
        ├── questions.csv        ← question content metadata
        └── lectures.csv         ← lecture content metadata
```

---

## KT4 File Format

Each file in `EdNet-KT4/` is named `u{user_id}.csv` and contains:

| Column | Type | Description |
|---|---|---|
| `timestamp` | int (ms) | Unix timestamp of the interaction |
| `solving_id` | int | Session/bundle ID |
| `question_id` | string | Question identifier (e.g., `q1234`) |
| `user_answer` | string | The answer the student chose |
| `elapsed_time` | int (ms) | Time taken to answer |
| `is_correct` | int (0/1) | Whether the answer was correct |
| `platform` | string | `mobile` or `web` |
| `item_id` | string | Content item ID |
| `user_id` | int | Anonymized student ID |
| `timestamp_seq` | int | Sequence order within the session |

---

## Contents File Format

**`questions.csv`**:

| Column | Description |
|---|---|
| `question_id` | Unique question ID |
| `bundle_id` | Bundle the question belongs to |
| `correct_answer` | The correct answer |
| `part` | Test section (1–7) |
| `tags` | Comma-separated skill/topic tags |

**`lectures.csv`**:

| Column | Description |
|---|---|
| `lecture_id` | Unique lecture ID |
| `tag` | Topic/skill tag |
| `part` | Test section (1–7) |
| `type_of` | Lecture type (`concept` / `solving` / etc.) |

---

## Using a Sample Subset

For demo or grading purposes, you can use a small subset:

```bash
# Create a sample from the first 100 user files only
mkdir -p data/EdNet-KT4
ls /path/to/extracted/KT4/ | head -100 | xargs -I{} cp /path/to/extracted/KT4/{} data/EdNet-KT4/

# Copy contents as-is
mkdir -p data/EdNet-Contents
cp /path/to/extracted/contents/questions.csv data/EdNet-Contents/
cp /path/to/extracted/contents/lectures.csv data/EdNet-Contents/
```

A subset of 100–1000 student files is sufficient to demonstrate the full pipeline end-to-end.

---

## Verification

Once the data is placed, verify the structure:

```bash
# On Linux / macOS / Git Bash
ls data/EdNet-KT4/ | head -5
ls data/EdNet-Contents/
```

Expected output:
```
u1.csv
u2.csv
u3.csv
...

questions.csv
lectures.csv
```

Then proceed to **[SETUP.md](./SETUP.md) Step 6**.
