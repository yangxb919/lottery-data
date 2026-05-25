import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_lottery_data as upd  # noqa: E402


def test_parse_ssq_row_normalizes_numbers():
    html = """
    <tbody id="tdata">
      <tr>
        <td>26057</td><td>1</td><td>10</td><td>22</td><td>24</td><td>28</td><td>30</td><td>7</td>
        <td></td><td>1,199,771,516</td><td></td><td></td><td></td><td></td><td></td><td>2026-05-21</td>
      </tr>
    </tbody>
    """

    records = upd.parse_rows(upd.CONFIGS["ssq"], html)

    assert records == [
        {
            "issue": "26057",
            "date": "2026-05-21",
            "red": ["01", "10", "22", "24", "28", "30"],
            "blue": ["07"],
            "source": "500.com",
        }
    ]


def test_parse_dlt_row_normalizes_numbers():
    html = """
    <tbody id="tdata">
      <tr>
        <td>26055</td><td>9</td><td>10</td><td>20</td><td>33</td><td>35</td><td>4</td><td>11</td>
        <td>757,078,646</td><td></td><td></td><td></td><td></td><td></td><td>2026-05-20</td>
      </tr>
    </tbody>
    """

    records = upd.parse_rows(upd.CONFIGS["dlt"], html)

    assert records == [
        {
            "issue": "26055",
            "date": "2026-05-20",
            "front": ["09", "10", "20", "33", "35"],
            "back": ["04", "11"],
            "source": "500.com",
        }
    ]


def test_merge_by_issue_replaces_existing_and_sorts_latest_first():
    existing = [
        {"issue": "26055", "date": "old"},
        {"issue": "26054", "date": "2026-05-18"},
    ]
    fresh = [
        {"issue": "26055", "date": "2026-05-20"},
        {"issue": "26056", "date": "2026-05-22"},
    ]

    merged = upd.merge_by_issue(existing, fresh)

    assert [item["issue"] for item in merged] == ["26056", "26055", "26054"]
    assert merged[1]["date"] == "2026-05-20"


def test_write_latest_is_stable_when_no_new_draw(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DATA_DIR", tmp_path)
    summary = [
        {
            "code": "ssq",
            "name": "双色球",
            "saved": 3454,
            "latest": {"issue": "26057", "date": "2026-05-21"},
        },
        {
            "code": "dlt",
            "name": "超级大乐透",
            "saved": 2873,
            "latest": {"issue": "26055", "date": "2026-05-20"},
        },
    ]

    upd.write_latest(summary)
    first = (tmp_path / "latest.json").read_text(encoding="utf-8")
    upd.write_latest(summary)
    second = (tmp_path / "latest.json").read_text(encoding="utf-8")

    assert first == second
    data = json.loads(first)
    assert "generated_at_utc" not in data
    assert data["summary"][0]["latest_issue"] == "26057"


def test_build_latest_summary_keeps_existing_other_lottery_on_partial_update(tmp_path, monkeypatch):
    monkeypatch.setattr(upd, "DATA_DIR", tmp_path)
    (tmp_path / "ssq.json").write_text(
        json.dumps(
            [
                {
                    "issue": "26058",
                    "date": "2026-05-24",
                    "red": ["01", "04", "07", "21", "29", "30"],
                    "blue": ["01"],
                    "source": "500.com",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "dlt.json").write_text(
        json.dumps(
            [
                {
                    "issue": "26056",
                    "date": "2026-05-23",
                    "front": ["06", "07", "18", "21", "30"],
                    "back": ["01", "05"],
                    "source": "500.com",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    latest_summary = upd.build_latest_summary(["ssq"])
    upd.write_latest(latest_summary)

    data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert set(data["lotteries"]) == {"ssq", "dlt"}
    assert data["lotteries"]["ssq"]["issue"] == "26058"
    assert data["lotteries"]["dlt"]["issue"] == "26056"

