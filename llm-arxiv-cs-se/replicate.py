"""
Replication of: "70% of new software engineering papers on arxiv are LLM-related"
https://shape-of-code.com/2026/03/22/70-of-new-software-engineering-papers-on-arxiv-are-llm-related/

Fetches cs.SE papers from arxiv since 2022-01-01, identifies LLM-related ones
via regex on title+abstract, and plots monthly prevalence.
"""

import re
import time
import pickle
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

import arxivscraper
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CACHE_FILE = Path("papers_cache.pkl")
START_DATE = date(2022, 1, 1)
END_DATE   = date(2026, 3, 22)   # match original post date

# Exact patterns from the original post (from the downloadable code link)
# https://shape-of-code.com/2026/03/22/70-of-new-software-engineering-papers-on-arxiv-are-llm-related/
LLM_RES = [
    re.compile(r'llm|large language model',   re.IGNORECASE),
    re.compile(r'ai[ ,.)]|artificial intellig', re.IGNORECASE),
    re.compile(r'agent',                       re.IGNORECASE),
]

def LLM_RE_search(text):
    return any(rx.search(text) for rx in LLM_RES)

def fetch_papers():
    """Fetch cs.SE papers in 3-month chunks to avoid timeouts."""
    if CACHE_FILE.exists():
        print("Loading cached papers...")
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)

    all_papers = []
    cursor = START_DATE
    while cursor < END_DATE:
        chunk_end = min(cursor + timedelta(days=90), END_DATE)
        print(f"Fetching {cursor} → {chunk_end} ...", flush=True)
        try:
            scraper = arxivscraper.Scraper(
                category="cs.SE",
                date_from=str(cursor),
                date_until=str(chunk_end),
                timeout=600,
            )
            papers = scraper.scrape()
            print(f"  got {len(papers)} papers")
            all_papers.extend(papers)
        except Exception as e:
            print(f"  ERROR: {e} — skipping chunk")
        cursor = chunk_end + timedelta(days=1)
        time.sleep(2)   # be polite

    with open(CACHE_FILE, "wb") as f:
        pickle.dump(all_papers, f)
    print(f"\nTotal papers fetched: {len(all_papers)}")
    return all_papers


def is_llm_related(paper):
    text = paper.get("title", "") + " " + paper.get("abstract", "")
    return LLM_RE_search(text)


def analyse(papers):
    monthly = defaultdict(lambda: {"total": 0, "llm": 0})
    for p in papers:
        # arxivscraper uses 'created' for original submission date
        raw = p.get("created", "") or p.get("updated", "")
        if not raw:
            continue
        month = str(raw)[:7]   # "YYYY-MM"
        # Only count papers first submitted in our window
        if month < "2022-01" or month > "2026-03":
            continue
        monthly[month]["total"] += 1
        if is_llm_related(p):
            monthly[month]["llm"] += 1

    rows = sorted(monthly.items())
    df = pd.DataFrame(
        [{"month": m, "total": v["total"], "llm": v["llm"]} for m, v in rows]
    )
    df["month"] = pd.to_datetime(df["month"])
    df["pct"] = 100 * df["llm"] / df["total"].replace(0, float("nan"))
    return df


def plot(df):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Top: absolute counts
    axes[0].bar(df["month"], df["total"], width=20, label="all cs.SE", alpha=0.5)
    axes[0].bar(df["month"], df["llm"],   width=20, label="LLM-related", alpha=0.8)
    axes[0].set_ylabel("Papers per month")
    axes[0].legend()
    axes[0].set_title("cs.SE papers on arxiv (Jan 2022 – Mar 2026)")

    # Bottom: percentage
    axes[1].plot(df["month"], df["pct"], marker="o", markersize=3, color="tab:red")
    axes[1].axhline(70, color="gray", linestyle="--", linewidth=0.8, label="70%")
    axes[1].set_ylabel("% LLM-related")
    axes[1].set_ylim(0, 105)
    axes[1].legend()
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate(rotation=45)

    plt.tight_layout()
    plt.savefig("result.png", dpi=150)
    print("Plot saved to result.png")


def print_summary(df):
    total_papers = df["total"].sum()
    total_llm    = df["llm"].sum()
    print(f"\n=== SUMMARY ===")
    print(f"Total cs.SE papers (Jan 2022 – Mar 2026): {total_papers}")
    print(f"LLM-related:                              {total_llm} ({100*total_llm/total_papers:.1f}%)")
    print()
    # Last 6 months before END_DATE
    recent = df[df["month"] >= "2025-10"]
    print("Monthly breakdown (Oct 2025 – Mar 2026):")
    print(recent[["month", "total", "llm", "pct"]].to_string(index=False))
    print()
    last = df.iloc[-1]
    print(f"Latest month ({last['month'].strftime('%Y-%m')}): {last['pct']:.1f}% LLM-related")


if __name__ == "__main__":
    papers = fetch_papers()
    df = analyse(papers)
    print_summary(df)
    plot(df)
