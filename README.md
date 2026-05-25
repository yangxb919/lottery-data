# China Lottery Data

自动抓取并保存中国彩票历史开奖数据：

- 双色球 `ssq`
- 超级大乐透 `dlt`

数据源：`https://datachart.500.com/`

## 项目边界

这个仓库只做 **开奖数据自动更新**，不做脚本化预测。

选号 / 预测参考由 Bowen 手动向 Hermes 下命令，并让 Hermes 加载 `ssq-dlt-llm-selection` skill 后，用大模型按方法论综合筛选。不要在仓库里新增 `generate_ai_prediction.py`、`ai_predictions.json` 或自动预测 workflow。

## 本地更新

```bash
python3 -m venv ~/.venvs/lottery-data
. ~/.venvs/lottery-data/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
python scripts/update_lottery_data.py
```

只更新双色球：

```bash
python scripts/update_lottery_data.py --lottery ssq
```

只更新大乐透：

```bash
python scripts/update_lottery_data.py --lottery dlt
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

GitHub Actions 在开奖日北京时间 22:05 自动运行，抓全量范围并按期号去重合并。若文件有变化，会自动提交到仓库。

覆盖开奖日：

- 双色球：周二、周四、周日
- 超级大乐透：周一、周三、周六
- 周五不跑，避免无效任务

手动触发：GitHub 仓库页面 → Actions → Update lottery data → Run workflow，可选择 `all` / `ssq` / `dlt`。

## Hermes 手动选号命令

需要双色球参考组合时，直接对 Hermes 说：

```text
使用 ssq-dlt-llm-selection skill，读取 /Users/yangxiaobo/Documents/Obsidian Prspares/Lottery/双色球大乐透开奖数据/data/ssq.json 最近30期和 data/latest.json，给我 5 组双色球参考组合。不要写脚本，不要自动预测，按 skill 方法论由大模型筛选。
```

科学选号不是预测中奖号，而是固定预算下的组合管理。

## JSON 示例

双色球：

```json
{
  "issue": "26058",
  "date": "2026-05-24",
  "red": ["01", "04", "07", "21", "29", "30"],
  "blue": ["01"],
  "source": "500.com"
}
```

大乐透：

```json
{
  "issue": "26056",
  "date": "2026-05-23",
  "front": ["06", "07", "18", "21", "30"],
  "back": ["01", "05"],
  "source": "500.com"
}
```
