# Buffer 快速筛选模型

基于 Panta 蛋白稳定性分析仪输出的 **8 项检测参数**，对候选 buffer 配方加权打分排序，用于在冻融实测前把候选集压缩到 3–4 个。

在线使用：部署后的 GitHub Pages 首页即为工具入口。

## 模型结构

评分 = 50 + 50 × [ wA × A + wB × B + 规则层 ]

| 维度 | 参数 | 方向 | 权重 |
|---|---|---|---|
| A 表面 / 胶体 | Radius | ↓ | 44.0% |
| | PDI | ↓ | 36.0% |
| B 构象稳定性 | Tm1 | ↑ | 6.0% |
| | Tonset | ↑ | 4.8% |
| | Tm2 | ↑ | 3.6% |
| | T_turbidity | ↑ | 3.2% |
| | T_scattering | ↑ | 1.2% |
| | T_size | ↑ | 1.2% |

**规则层**（配方硬规则，实际起作用最大的部分）

- 磷酸盐体系（PBS）：罚分 −3.0 —— 第一轮 3/3 全部落入高危档（39,239–47,142）
- 渗透保护剂（蔗糖 / 海藻糖 / 山梨醇）：粒径惩罚豁免 ×0.10 + 机制加分 +1.50 —— 两轮 2/2 落入最优档

## 验证结果

| 指标 | 值 |
|---|---|
| 轮内排序相关（Spearman ρ） | +0.70 / +0.64 |
| 嵌套留一（规则参数折内重选） | +0.70 / +0.64 |
| Top3 命中率 | 33% / 67%（随机基线 25%） |

权重不是自由拟合的结果：n=23 时 8 个自由权重不可识别（PDI 与「含蔗糖」相关 r=0.74，存在辛普森悖论），任何拟合权重表都只是在记忆噪声。因此采用 **物理方向锁定 → 结构消融定幅度 → 留一法验证整体** 的流程。

## 使用

1. 打开工具页，按项目阶段选择权重档位（默认 / 只看胶体 / 稳定性优先）
2. 在 Excel 中选中候选参数区域复制，点「粘贴 Excel 数据」导入（支持乱序表头、单位后缀、缺失标记）
3. 按评分降序取前 3–4 名送冻融实测

**能力边界**：工具用于粗筛淘汰明显高风险配方，Top3 命中率约 1/3–2/3，不能精确挑出唯一最优。建议前 3–4 名全部进入实测。

## 文件

```
index.html                     入口页
Buffer快速筛选工具.html          交互式筛选工具（单文件，纯前端）
分析报告.md                     权重依据、验证过程、结论
data/buffer_screening.csv      两轮标定数据（n=23）
data/buffer_screening_extended.csv  扩展模板（表面性质指标待补测）
model/eight_param_model.json   权重与验证指标
scripts/final_weights.py       权重标定与嵌套留一验证
scripts/eight_param_model.py   权重消融与结构搜索
scripts/extend_study.py        bridge study：新指标纳入判据评估
```

## 复现

```bash
python -m venv .venv && .venv/Scripts/pip install numpy pandas scipy scikit-learn
python scripts/final_weights.py
```

新数据回填 `data/buffer_screening.csv` 后重跑脚本即可更新权重。

## 下一步

现有 8 项参数的信息量已接近上限。要提升 Top3 命中率，需补表面性质维度：ζ 电位、疏水性（HIC 相对保留）、SEC 聚集体%、DLS 计数率。`scripts/extend_study.py` 已内置三条纳入判据，补测数据填入扩展模板后直接运行即可判定「进权重 / 进红旗 / 弃用」。
