#!/usr/bin/env python3
"""
Fill demodata.csv with raw demographic counts from raw_data zip files.
Each zip contains a district-data.csv from Dave's Redistricting App.

Race notes (DRA definitions):
  - White  = White alone, NOT Hispanic
  - Black  = Black alone or in combination (INCLUDES Hispanic Blacks)
  - Asian  = Asian alone or in combination (INCLUDES Hispanic Asians)
  - Hispanic = All Hispanics regardless of race
  - Other  = Native + Pacific (these are the remaining DRA race fields)
  Categories overlap by design; they do not sum to total population.

Age note: DRA provides age buckets starting at 0-9, 10-19, 20-29 ...
  "18 to 29" is approximated by the 20-29 bucket (18-19 not available).
"""

import csv
import io
import os
import zipfile

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")
DEMODATA_PATH = os.path.join(os.path.dirname(__file__), "demodata.csv")


def parse_district_csv(zip_path):
    """Extract and parse district-data.csv from a state zip file."""
    state = os.path.splitext(os.path.basename(zip_path))[0].upper()
    rows = {}
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("district-data.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                if row["ID"] == "0":  # skip unassigned placeholder
                    continue
                label = row["Label"].strip()
                district_code = f"{state}-{int(label):02d}"
                rows[district_code] = row
    return rows


def get(row, key):
    """Return int value of a raw data field, defaulting to 0."""
    return int(float(row.get(key) or 0))


def compute_demographics(row):
    """Return raw counts for all demodata columns from a DRA district row."""

    # --- Race (2020 Census total population) ---
    # Some states use CENS_ADJ (adjusted for incarcerated persons) instead of CENS.
    # Fall back to ADJ columns when the standard ones are absent.
    def race(field):
        val = get(row, f"T_20_CENS_{field}")
        if val == 0:
            val = get(row, f"T_20_CENS_ADJ_{field}")
        return val

    white    = race("White")
    hispanic = race("Hispanic")
    black    = race("Black")
    asian    = race("Asian")
    native   = race("Native")
    pacific  = race("Pacific")
    other    = native + pacific

    # --- Age (2022 ACS) ---
    # Note: 20-29 bucket used as proxy for "18 to 29" (18-19 not in DRA data)
    age_18_29  = get(row, "X_22_2022_Age_Age_20_29")
    age_30_49  = get(row, "X_22_2022_Age_Age_30_39") + get(row, "X_22_2022_Age_Age_40_49")
    age_50_69  = get(row, "X_22_2022_Age_Age_50_59") + get(row, "X_22_2022_Age_Age_60_69")
    age_70plus = get(row, "X_22_2022_Age_Age_70_79") + get(row, "X_22_2022_Age_Age_O79")

    # --- Education (2022 ACS, adults 25+) ---
    hs_or_less   = get(row, "X_22_2022_Education_NoHS") + get(row, "X_22_2022_Education_HS")
    some_college = get(row, "X_22_2022_Education_SomeCol")
    associates   = get(row, "X_22_2022_Education_Assoc")
    bach_or_more = (get(row, "X_22_2022_Education_Bach") +
                    get(row, "X_22_2022_Education_Master") +
                    get(row, "X_22_2022_Education_Prof") +
                    get(row, "X_22_2022_Education_Doc"))

    # --- Income (2022 ACS households) ---
    inc_25k_or_less  = (get(row, "X_22_2022_Household_Income_U10K") +
                        get(row, "X_22_2022_Household_Income_10_15K") +
                        get(row, "X_22_2022_Household_Income_15_20K") +
                        get(row, "X_22_2022_Household_Income_20_25K"))
    inc_25k_to_50k   = (get(row, "X_22_2022_Household_Income_25_30K") +
                        get(row, "X_22_2022_Household_Income_30_35K") +
                        get(row, "X_22_2022_Household_Income_35_40K") +
                        get(row, "X_22_2022_Household_Income_40_45K") +
                        get(row, "X_22_2022_Household_Income_45_50K"))
    inc_50k_to_75k   = (get(row, "X_22_2022_Household_Income_50_60K") +
                        get(row, "X_22_2022_Household_Income_60_75K"))
    inc_75k_to_100k  =  get(row, "X_22_2022_Household_Income_75_100K")
    inc_100k_or_more = (get(row, "X_22_2022_Household_Income_100_125K") +
                        get(row, "X_22_2022_Household_Income_125_150K") +
                        get(row, "X_22_2022_Household_Income_150_200K") +
                        get(row, "X_22_2022_Household_Income_O200K"))

    return {
        "White":                 white,
        "Asian":                 asian,
        "Black":                 black,
        "Hispanic":              hispanic,
        "Other":                 other,
        "18 to 29":              age_18_29,
        "30 to 49":              age_30_49,
        "50 to 69":              age_50_69,
        "70+":                   age_70plus,
        "HS or less":            hs_or_less,
        "Some college":          some_college,
        "Associate's":           associates,
        "Bachelor's or greater": bach_or_more,
        "25k or less":           inc_25k_or_less,
        "25k to 50k":            inc_25k_to_50k,
        "50k to 75k":            inc_50k_to_75k,
        "75k to 100k":           inc_75k_to_100k,
        "100k or greater":       inc_100k_or_more,
    }


def main():
    # Build lookup: district_code -> raw DRA row
    all_districts = {}
    for fname in sorted(os.listdir(RAW_DATA_DIR)):
        if not fname.endswith(".zip"):
            continue
        zip_path = os.path.join(RAW_DATA_DIR, fname)
        try:
            districts = parse_district_csv(zip_path)
            all_districts.update(districts)
        except Exception as e:
            print(f"Warning: could not process {fname}: {e}")

    print(f"Loaded {len(all_districts)} districts from raw_data.")

    # Read existing demodata.csv
    with open(DEMODATA_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        original_rows = list(reader)

    # Fill in values
    updated = 0
    missing = []
    for row in original_rows:
        code = row["District Code"]
        if code in all_districts:
            row.update(compute_demographics(all_districts[code]))
            updated += 1
        else:
            missing.append(code)

    # Write back
    with open(DEMODATA_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(original_rows)

    print(f"Updated {updated} rows.")
    if missing:
        print(f"No raw data found for {len(missing)} districts: {missing}")


if __name__ == "__main__":
    main()
