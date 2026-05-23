#!/usr/bin/env python3
"""Fetch and persist China lottery draw history.

Supported lotteries:
- ssq: 双色球, 500.com datachart
- dlt: 超级大乐透, 500.com datachart

The script is intentionally idempotent:
1. Fetches the full historical range on every run.
2. Merges by issue number with existing JSON files.
3. Writes only normalized JSON, latest first.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE = "500.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://www.500.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass(frozen=True)
class LotteryConfig:
    code: str
    name: str
    start_issue: str
    url: str
    red_max: int
    blue_max: int


CONFIGS: Dict[str, LotteryConfig] = {
    "ssq": LotteryConfig(
        code="ssq",
        name="双色球",
        start_issue="03001",
        url="https://datachart.500.com/ssq/history/newinc/history.php",
        red_max=33,
        blue_max=16,
    ),
    "dlt": LotteryConfig(
        code="dlt",
        name="超级大乐透",
        start_issue="07001",
        url="https://datachart.500.com/dlt/history/newinc/history.php",
        red_max=35,
        blue_max=12,
    ),
}


class LotteryDataError(RuntimeError):
    pass


def current_year_end_issue() -> str:
    """Use YY200 as a safe current-year upper bound."""
    return f"{datetime.now().year % 100:02d}200"


def normalize_ball(text: str) -> str:
    value = re.sub(r"\D", "", text or "")
    if not value:
        raise LotteryDataError(f"empty ball value: {text!r}")
    return f"{int(value):02d}"


def validate_unique_range(values: Iterable[str], low: int, high: int, label: str) -> None:
    nums = [int(v) for v in values]
    if len(nums) != len(set(nums)):
        raise LotteryDataError(f"{label} numbers are not unique: {values}")
    for n in nums:
        if not (low <= n <= high):
            raise LotteryDataError(f"{label} number out of range {low}-{high}: {n}")


def fetch_html(cfg: LotteryConfig, start_issue: str, end_issue: str) -> str:
    params = {"start": start_issue, "end": end_issue}
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(cfg.url, params=params, headers=HEADERS, timeout=40)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            if "tdata" not in resp.text:
                raise LotteryDataError(f"{cfg.code} response missing tbody#tdata")
            return resp.text
        except Exception as exc:  # noqa: BLE001 - retry network/parser guard
            last_error = exc
            if attempt < 3:
                time.sleep(2 * attempt)
            else:
                break
    raise LotteryDataError(f"failed to fetch {cfg.code}: {last_error}")


def parse_rows(cfg: LotteryConfig, html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tbody#tdata tr")
    if not rows:
        raise LotteryDataError(f"no rows parsed for {cfg.code}")

    records: List[Dict[str, Any]] = []
    for row in rows:
        cols = [c.get_text(strip=True).replace("\xa0", "") for c in row.select("td")]
        if not cols:
            continue
        issue = cols[0]
        if not re.fullmatch(r"\d{5}", issue):
            continue
        date = cols[-1]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue

        if cfg.code == "ssq":
            if len(cols) < 8:
                continue
            red = [normalize_ball(v) for v in cols[1:7]]
            blue = [normalize_ball(cols[7])]
            validate_unique_range(red, 1, cfg.red_max, "ssq red")
            validate_unique_range(blue, 1, cfg.blue_max, "ssq blue")
            records.append(
                {
                    "issue": issue,
                    "date": date,
                    "red": red,
                    "blue": blue,
                    "source": SOURCE,
                }
            )
        elif cfg.code == "dlt":
            if len(cols) < 8:
                continue
            front = [normalize_ball(v) for v in cols[1:6]]
            back = [normalize_ball(v) for v in cols[6:8]]
            validate_unique_range(front, 1, cfg.red_max, "dlt front")
            validate_unique_range(back, 1, cfg.blue_max, "dlt back")
            records.append(
                {
                    "issue": issue,
                    "date": date,
                    "front": front,
                    "back": back,
                    "source": SOURCE,
                }
            )

    if not records:
        raise LotteryDataError(f"no valid records parsed for {cfg.code}")
    return records


def read_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise LotteryDataError(f"{path} must contain a JSON array")
    return data


def merge_by_issue(existing: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for item in existing + fresh:
        issue = str(item.get("issue", "")).strip()
        if issue:
            merged[issue] = item
    return sorted(merged.values(), key=lambda x: int(x["issue"]), reverse=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def update_one(code: str, end_issue: str) -> Dict[str, Any]:
    cfg = CONFIGS[code]
    out_path = DATA_DIR / f"{code}.json"
    html = fetch_html(cfg, cfg.start_issue, end_issue)
    fresh = parse_rows(cfg, html)
    existing = read_json_list(out_path)
    merged = merge_by_issue(existing, fresh)
    write_json(out_path, merged)

    latest = merged[0]
    added_or_replaced = len({r["issue"] for r in fresh} - {r.get("issue") for r in existing})
    return {
        "code": code,
        "name": cfg.name,
        "path": str(out_path.relative_to(ROOT)),
        "fetched": len(fresh),
        "existing_before": len(existing),
        "saved": len(merged),
        "new_issues": added_or_replaced,
        "latest": latest,
        "source_url": f"{cfg.url}?start={cfg.start_issue}&end={end_issue}",
    }


def write_latest(summary: List[Dict[str, Any]]) -> None:
    latest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "lotteries": {item["code"]: item["latest"] for item in summary},
        "summary": [
            {
                "code": item["code"],
                "name": item["name"],
                "saved": item["saved"],
                "latest_issue": item["latest"]["issue"],
                "latest_date": item["latest"]["date"],
            }
            for item in summary
        ],
    }
    write_json(DATA_DIR / "latest.json", latest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update SSQ/DLT lottery history JSON files")
    parser.add_argument(
        "--lottery",
        choices=["all", *CONFIGS.keys()],
        default="all",
        help="Lottery to update. Default: all",
    )
    parser.add_argument(
        "--end-issue",
        default=current_year_end_issue(),
        help="Upper issue bound in YYNNN format. Default: current YY200",
    )
    args = parser.parse_args()

    codes = list(CONFIGS.keys()) if args.lottery == "all" else [args.lottery]
    summary = [update_one(code, args.end_issue) for code in codes]
    write_latest(summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI level guard
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
