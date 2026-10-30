# 八字命理知识数据库 v2

v2 在 v1 骨架上继续扩了三大块，并把“可离线直接用的数据”和“需要联网导入的大型开放语料”分开，避免为了凑数量而伪造命例。

## A. 已经直接装进 ZIP 的规则层

| 数据 | 条数 |
|---|---:|
| 六十日柱 | 60 |
| 60日柱 × 12月 | 720 |
| **60日柱 × 12时辰** | **720** |
| 十神关系矩阵 | 100 |
| **十神坐十神** | **100** |
| **十神落四柱** | **40** |
| **六亲/婚姻/事业/财运/子女专题规则卡** | **800** |
| **六亲星具体映射（日主×性别×关系）** | **160** |

这些都是结构化规则，不冒充古籍原句；字段中明确写了 `source_type / rule_origin / confidence / is_quote`。

### 关键新增文件

- `day_hour_720.json/csv`  
  60日柱 × 十二时辰，自动按五鼠遁计算时干/时柱、时干十神、藏干十神、日支-时支关系、十二长生。
- `ten_god_sits_ten_god_100.json/csv`
- `ten_god_by_pillar_40.json/csv`
- `topic_rules_800.json/jsonl/csv`
- `six_relatives_matrix_160.json/csv`
- `website_adapter_v2.js`

## B. 公版古籍全文层

`classics_ingest_manifest.json` 已登记首批 8 个高优先级公版古籍根源：

1. 《三命通会》四库本
2. 《五行精纪》
3. 《珞琭子三命消息赋注》四库本
4. 《李虚中命书》四库本
5. 《滴天髓》古籍原文
6. 《神峰通考》
7. 《穷通宝鉴》
8. 《渊海子平大全》

运行：

```bat
python scripts\ingest_public_domain_wikisource.py
```

脚本会：
- 从维基文库读取根页；
- 自动发现同书卷章；
- 抽取纯文本；
- 去重；
- 约 1100 字/片、120 字重叠进行切片；
- 写入 `imported/classics_public_domain_chunks.jsonl`；
- 每条保留 `book / page_title / source_url / rights / sha1`。

**只抓公版古籍原文，不把现代作者注释当成“古籍原文”。**

## C. 1000+ 真实人物命盘 / 真实断案

这里刻意分成两层：

### 1. 公众人物命盘底库：2,284 人

开放数据：`shunshi-ai/east-asian-celebrity-bazi`，CC BY 4.0。

它有姓名、生日、年/月/日三柱、五行、十神、藏干、日主和部分格局标签。  
**没有可靠出生时辰的人绝不补造时柱**；数据源本身也明确这样做。

### 2. 有已记录真实人生事件的高质量断案：63 人 / 295 题

开放数据：`shunshi-ai/fate-bench`。

它包含真实命主的出生年月日时、地点、完整四柱、大运以及事后核实的人生事件问答；答案有 `answer_provenance`，可以只使用官方公布的部分。

运行：

```bat
python scripts\ingest_open_case_datasets.py
```

会生成：

- `imported/cases_master_open.jsonl`
  - 2,284 位公众人物三柱 case seed
  - 63 位有完整时辰/大运/事件的 Fate-Bench case
- `imported/events_verified_qa.jsonl`
  - 295 条事件问答/验证层
- `imported/case_import_summary.json`

未去重前 case 行目标约 **2,347**。导入脚本不会把 BaziQA / MingLi-Bench 与 Fate-Bench 的 vendor 数据重复叠加来虚报数量。

## Windows 最简单方法

双击：

`一键扩库_Windows.cmd`

它依次完成：

1. 公版古籍全文切片
2. 开放真实案例导入
3. 生成前端数据索引

## 网站调用

```html
<script src="./data/website_adapter_v2.js"></script>
<script>
const db = await BaziDB2.loadCore("./data/");
console.log(BaziDB2.dayHour(db, "甲寅", "辰"));
console.log(BaziDB2.tenGodSits(db, "正官", "正印"));
console.log(BaziDB2.topic(db, "婚姻", {ten_god:"正财", pillar:"日柱"}));
</script>
```

## 数据伦理/质量边界

- “古籍原文”与“现代整理”必须分层。
- “公众人物生日命盘”与“有事件核实的断案”必须分层。
- 没有出生时辰，不补造时柱。
- 不把规则模板冒充古籍原句。
- 现代知乎/搜狐/文库等只保存规则摘要、来源和链接，不整篇镜像。
- 命理属于传统文化体系，不是经过现代科学验证的预测模型。
