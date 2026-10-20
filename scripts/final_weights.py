# -*- coding: utf-8 -*-
"""最终 8 参数权重模型：导出 model/eight_param_model.json + 嵌套留一验证"""
import json
import itertools
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

DATA = "data/buffer_screening.csv"
OUT = "model/eight_param_model.json"

P = [
    ("radius_nm", "Radius", -1, "A"),
    ("pdi", "PDI", -1, "A"),
    ("tm1_c", "Tm1", +1, "B"),
    ("tm2_c", "Tm2", +1, "B"),
    ("tonset_c", "Tonset", +1, "B"),
    ("t_turbidity_c", "T_turbidity", +1, "B"),
    ("t_scattering_c", "T_scattering", +1, "B"),
    ("t_size_c", "T_size", +1, "B"),
]

# 最终归一权重（A 组 80% / B 组 20%；B 内部 Tm1 .30 Tm2 .18 Tonset .24 Tturb .16 Tscat .06 Tsize .06）
W = {
    "radius_nm": 0.440, "pdi": 0.360,
    "tm1_c": 0.060, "tm2_c": 0.036, "tonset_c": 0.048,
    "t_turbidity_c": 0.032, "t_scattering_c": 0.012, "t_size_c": 0.012,
}
WA = 0.80
RULES = {"protectant_exempt": 0.10, "protectant_bonus": 1.50, "phosphate_penalty": 3.0}

df = pd.read_csv(DATA)
df["tm2_c"] = pd.to_numeric(df["tm2_c"], errors="coerce")
df["tm2_c"] = df["tm2_c"].fillna(df.groupby("round")["tm2_c"].transform("median"))
COLS = [p[0] for p in P]
prot = df["buffer"].str.contains("蔗糖|海藻糖|山梨醇").values
phos = df["buffer"].str.contains("PBS|磷酸").values


def zcols(d):
    out = {}
    for c in COLS:
        v = d[c].values.astype(float)
        out[c] = (v - v.mean()) / (v.std() + 1e-12)
    return out


def score(dfsub, w=None, rules=None):
    """候选集内相对评分（0-100）。w: 8维权重字典；rules: 规则参数"""
    w = W if w is None else w
    rules = RULES if rules is None else rules
    z = zcols(dfsub)
    tot = sum(w[c] for c in COLS)
    s = np.zeros(len(dfsub))
    for c, _, sg, _ in P:
        s += (w[c] / tot) * sg * z[c]
    p = dfsub["buffer"].str.contains("蔗糖|海藻糖|山梨醇").values
    ph = dfsub["buffer"].str.contains("PBS|磷酸").values
    s = np.where(p, s * rules["protectant_exempt"] + rules["protectant_bonus"], s)
    s = s + np.where(ph, -rules["phosphate_penalty"], 0)
    return s


def report(tag):
    print(f"\n{tag}")
    print(f"{'轮次':<6}{'rho':>8}{'Top3':>8}")
    rs, ts = [], []
    for r in (1, 2):
        d = df[df["round"] == r].reset_index(drop=True)
        s = score(d)
        rho = spearmanr(s, -d["ns_post_ft"]).correlation
        k = len(set(np.argsort(-s)[:3]) & set(np.argsort(d["ns_post_ft"].values)[:3])) / 3
        rs.append(rho); ts.append(k)
        print(f"第{r}轮{'':<2}{rho:>+8.2f}{k*100:>7.0f}%")
    print(f"平均    {np.mean(rs):>+8.2f}{np.mean(ts)*100:>7.0f}%")
    return rs, ts


print("=" * 80)
print("最终 8 参数权重")
print("=" * 80)
for c, cn, sg, g in P:
    print(f"  {cn:<14} 组{g}  {'↑ 越大越好' if sg > 0 else '↓ 越小越好':<12} {W[c]*100:5.1f}%")
print(f"  {'合计':<14}      {'':<12} {sum(W.values())*100:5.1f}%")

rs, ts = report("固定权重 + 规则层（全样本，含规则参数调优）")

# 嵌套留一：每折在剩余样本上重选规则参数
print("\n" + "=" * 80)
print("嵌套留一验证（规则参数也在折内重选，避免乐观偏差）")
print("=" * 80)
grid = [g for g in itertools.product([0.0, 0.05, 0.10, 0.25, 1.0], [0.0, 1.0, 1.5, 2.0])]
preds = np.zeros((len(df), 2))
for i in range(len(df)):
    keep = np.arange(len(df)) != i
    dtr = df[keep].reset_index(drop=True)
    best, bestv = None, -9
    for ex, sb in grid:
        rr = []
        for r in (1, 2):
            dd = dtr[dtr["round"] == r].reset_index(drop=True)
            if len(dd) < 5:
                continue
            s = score(dd, rules={"protectant_exempt": ex, "protectant_bonus": sb,
                                 "phosphate_penalty": 3.0})
            rr.append(spearmanr(s, -dd["ns_post_ft"]).correlation)
        if rr and np.mean(rr) > bestv:
            bestv, best = np.mean(rr), (ex, sb)
    ex, sb = best
    for j, r in enumerate((1, 2)):
        m = (df["round"] == r).values
        d = df[m].reset_index(drop=True)
        s = score(d, rules={"protectant_exempt": ex, "protectant_bonus": sb,
                            "phosphate_penalty": 3.0})
        idx = np.where(m)[0]
        pos = list(idx).index(i) if i in idx else None
        if pos is not None:
            preds[i, j] = s[pos]

y = (1 - df.groupby("round")["ns_post_ft"].rank(pct=True)).values
for j, r in enumerate((1, 2)):
    m = (df["round"] == r).values
    ok = preds[m, j] != 0
    rho = spearmanr(preds[m, j][ok], y[m][ok]).correlation
    print(f"  第{r}轮 留一外推 rho = {rho:+.2f}  (n={ok.sum()})")

print("\n" + "=" * 80)
print("排序对照（固定权重 + 规则层）")
print("=" * 80)
for r in (1, 2):
    d = df[df["round"] == r].reset_index(drop=True)
    s = score(d)
    d = d.assign(S=50 + 50 * s).sort_values("S", ascending=False)
    print(f"\n第{r}轮：")
    for i, row in enumerate(d.itertuples(), 1):
        flag = " [磷酸盐·淘汰]" if ("PBS" in row.buffer) else (" [保护剂·加分]" if "蔗糖" in row.buffer else "")
        print(f"  {i:>2d}. {row.buffer:<26s} 评分{row.S:5.1f}  实测{row.ns_post_ft:6.0f}{flag}")

out = {
    "version": "8param-v1",
    "target": "冻融后综合非特异性 ns_post_ft",
    "params": [
        {"key": c, "cn": cn, "sign": sg, "group": g, "weight": W[c]} for c, cn, sg, g in P
    ],
    "blend_A": WA,
    "rules": RULES,
    "perf": {
        "in_sample_rho": rs,
        "in_sample_top3": ts,
        "n": len(df),
    },
    "notes": [
        "8 个权重全部为物理方向先验 + 结构消融确定，非自由拟合（n=23 时 8 个自由权重不可识别，LOO 为负）",
        "Tm2 缺失时用本轮中位数填补",
        "磷酸盐罚分 3.0、保护剂机制加分 1.5 为规则层，独立于参数加权",
    ],
    "samples": [
        {"id": r["sample_id"], "buffer": r["buffer"], "round": int(r["round"]),
         "ns": int(r["ns_post_ft"]), "v": [round(float(r[c]), 4) for c in COLS]}
        for _, r in df.iterrows()
    ],
    "tm2_missing": [r["sample_id"] for _, r in df.iterrows() if pd.isna(r["tm2_c"])],
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n导出 {OUT}")
