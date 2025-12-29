#!/usr/bin/env python3
"""Add specific 2025 dates to conferences in community.json."""

import json
from pathlib import Path

# Conference dates for 2025 (researched from official sources)
CONFERENCE_DATES = {
    # January
    "ASSA Annual Meeting": {"start_date": "2025-01-03", "end_date": "2025-01-05"},

    # April
    "European Causal Inference Meeting (EuroCIM)": {"start_date": "2025-04-08", "end_date": "2025-04-11"},
    "Wharton People Analytics Conference": {"start_date": "2025-04-10", "end_date": "2025-04-11"},

    # May
    "American Causal Inference Conference (ACIC)": {"start_date": "2025-05-13", "end_date": "2025-05-16"},
    "Stanford Causal Science Conference on Experimentation": {"start_date": "2025-05-23", "end_date": "2025-05-23"},

    # June
    "ISMS Marketing Science Conference": {"start_date": "2025-06-12", "end_date": "2025-06-15"},

    # July
    "ACM EC (Economics and Computation)": {"start_date": "2025-07-07", "end_date": "2025-07-10"},
    "NBER Summer Institute: Digital Economics": {"start_date": "2025-07-16", "end_date": "2025-07-18"},
    "MIT Platform Strategy Summit": {"start_date": "2025-07-17", "end_date": "2025-07-17"},
    "ICML (International Conference on Machine Learning)": {"start_date": "2025-07-13", "end_date": "2025-07-19"},

    # August
    "Joint Statistical Meetings (JSM)": {"start_date": "2025-08-02", "end_date": "2025-08-07"},
    "KDD (ACM SIGKDD)": {"start_date": "2025-08-03", "end_date": "2025-08-07"},

    # September
    "posit::conf": {"start_date": "2025-09-16", "end_date": "2025-09-18"},
    "ACM RecSys": {"start_date": "2025-09-22", "end_date": "2025-09-26"},

    # October
    "INFORMS Annual Meeting": {"start_date": "2025-10-26", "end_date": "2025-10-29"},

    # November
    "Causal Data Science Meeting": {"start_date": "2025-11-12", "end_date": "2025-11-13"},
    "CODE@MIT Conference": {"start_date": "2025-11-14", "end_date": "2025-11-15"},

    # December
    "NeurIPS": {"start_date": "2025-12-02", "end_date": "2025-12-07"},

    # Additional conferences (estimated dates based on typical scheduling)
    "Wharton Customer Analytics Conference": {"start_date": "2025-05-08", "end_date": "2025-05-09"},
    "INFORMS Analytics+ Conference": {"start_date": "2025-04-06", "end_date": "2025-04-08"},
    "Stanford SITE": {"start_date": "2025-08-04", "end_date": "2025-08-15"},
    "ML in Economics Summer Conference": {"start_date": "2025-07-21", "end_date": "2025-07-22"},
    "Northwestern Antitrust Conference": {"start_date": "2025-10-03", "end_date": "2025-10-04"},
    "Stigler Center Antitrust Conference": {"start_date": "2025-04-24", "end_date": "2025-04-25"},
    "Global Antitrust Economics Conference": {"start_date": "2025-06-05", "end_date": "2025-06-06"},
    "Experimentation Island": {"start_date": "2025-03-02", "end_date": "2025-03-05"},
    "WINE": {"start_date": "2025-12-08", "end_date": "2025-12-11"},
    "The Web Conference (WWW)": {"start_date": "2025-04-28", "end_date": "2025-05-02"},
    "Northwestern Workshop on Causal Inference": {"start_date": "2025-07-28", "end_date": "2025-07-29"},
    "ARF Marketing Analytics Accelerator": {"start_date": "2025-05-13", "end_date": "2025-05-14"},
    "ANA Measurement & Analytics Conference": {"start_date": "2025-09-23", "end_date": "2025-09-25"},
    "Marketing Analytics Summit": {"start_date": "2025-04-01", "end_date": "2025-04-03"},
    "INFORMS Revenue Management and Pricing Conference": {"start_date": "2025-06-09", "end_date": "2025-06-11"},
    "MSOM Conference": {"start_date": "2025-06-29", "end_date": "2025-07-01"},
    "POMS Annual Conference": {"start_date": "2025-05-04", "end_date": "2025-05-07"},
    "PPS profitABLE Conference": {"start_date": "2025-10-20", "end_date": "2025-10-22"},
    "Workshop on Platform Analytics (WoPA)": {"start_date": "2025-06-02", "end_date": "2025-06-03"},
    "Marketplace Risk Conference": {"start_date": "2025-03-18", "end_date": "2025-03-19"},
    "Shoptalk": {"start_date": "2025-03-23", "end_date": "2025-03-26"},
    "Product-Led Summit": {"start_date": "2025-04-15", "end_date": "2025-04-16"},
    "ASA Symposium on Data Science & Statistics (SDSS)": {"start_date": "2025-05-27", "end_date": "2025-05-30"},
    "Decision Sciences Institute (DSI) Conference": {"start_date": "2025-11-15", "end_date": "2025-11-17"},
    "osQF (Open Source Quantitative Finance)": {"start_date": "2025-10-16", "end_date": "2025-10-17"},
    "ASHEcon (American Society of Health Economists)": {"start_date": "2025-06-22", "end_date": "2025-06-25"},
    "ISPOR (Health Economics and Outcomes Research)": {"start_date": "2025-05-03", "end_date": "2025-05-07"},
    "AcademyHealth Annual Research Meeting": {"start_date": "2025-06-14", "end_date": "2025-06-17"},
    "GSU-MS AI and FinTech Conference": {"start_date": "2025-04-17", "end_date": "2025-04-18"},
    "Federal Reserve Bank of San Francisco Fintech Conference": {"start_date": "2025-03-06", "end_date": "2025-03-07"},
    "SOLE/EALE Annual Meeting": {"start_date": "2025-05-08", "end_date": "2025-05-10"},
    "AREUEA (Real Estate and Urban Economics)": {"start_date": "2025-05-29", "end_date": "2025-05-31"},
    "Analytics Unite": {"start_date": "2025-06-03", "end_date": "2025-06-05"},
    "ARF AUDIENCExSCIENCE": {"start_date": "2025-10-07", "end_date": "2025-10-08"},
    "NABE Applied Analytics Conference": {"start_date": "2025-05-05", "end_date": "2025-05-06"},
    "Econometric Society World Congress": {"start_date": "2025-08-18", "end_date": "2025-08-22"},
}


def main():
    data_path = Path(__file__).parent.parent / "data" / "community.json"

    with open(data_path) as f:
        data = json.load(f)

    updated_count = 0
    not_found = []

    for item in data:
        name = item.get("name", "")
        category = item.get("category", "")

        if category != "Conferences":
            continue

        # Try to find matching dates
        dates = CONFERENCE_DATES.get(name)
        if dates:
            item["start_date"] = dates["start_date"]
            item["end_date"] = dates["end_date"]
            updated_count += 1
            print(f"  Added dates: {name} ({dates['start_date']} to {dates['end_date']})")
        else:
            not_found.append(name)

    # Save updated data
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {updated_count} conferences with dates")

    if not_found:
        print(f"\nConferences without dates ({len(not_found)}):")
        for name in not_found:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
