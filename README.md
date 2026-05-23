# China Lottery Data

自动抓取并保存中国彩票历史开奖数据：

- 双色球 `ssq`
- 超级大乐透 `dlt`

数据源：`https://datachart.500.com/`

## 本地更新

```bash
python3 -m venv ~/.venvs/lottery-data
. ~/.venvs/lottery-data/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
python scripts/update_lottery_data.py
```

## 输出文件

```text
data/ssq.json      # 双色球历史，最新在前
data/dlt.json      # 大乐透历史，最新在前
data/latest.json   # 两种彩票最新一期汇总
```

Raw JSON：

```text
https://raw.githubusercontent.com/yangxb919/lottery-data/main/data/ssq.json
https://raw.githubusercontent.com/yangxb919/lottery-data/main/data/dlt.json
https://raw.githubusercontent.com/yangxb919/lottery-data/main/data/latest.json
```

## 自动更新

GitHub Actions 每天北京时间 22:05 自动运行一次，抓全量范围并按期号去重合并。若文件有变化，会自动提交到仓库。

手动触发：GitHub 仓库页面 → Actions → Update lottery data → Run workflow。

## JSON 示例

双色球：

```json
{
  "issue": "26057",
  "date": "2026-05-21",
  "red": ["01", "10", "22", "24", "28", "30"],
  "blue": ["07"],
  "source": "500.com"
}
```

大乐透：

```json
{
  "issue": "26055",
  "date": "2026-05-20",
  "front": ["09", "10", "20", "33", "35"],
  "back": ["04", "11"],
  "source": "500.com"
}
```
