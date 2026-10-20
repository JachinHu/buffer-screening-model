# -*- coding: utf-8 -*-
"""8 参数权重模型：Panta 输出的 8 个检测参数 -> 综合非特异性（冻融后）
参数：Radius / PDI / Tm1 / Tm2 / Tonset / T_turbidity / T_scattering / T_size
"""
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from scipy.optimize import nnls
from sklearn.linear_model import Ridge

DATA = "data/buffer_screening.csv"
OUT = "model/eight_param_model.json"

P = [
    ("radius_nm", "Radius", -1),
    ("pdi", "PDI", -1),
    ("tm1_c", "Tm1", +1),
    ("tm2_c", "Tm2", +1),
    ("tonset_c", "Tonset", +1),
    ("t_turbidity_c", "T_turbidity", +1),
    ("t_scattering_c", "T_scattering", +1),
    ("t_size_c", "T_size", +1),
]
COLS = [p[0] for p in P]
SIGN = {p[0]: p[2] for p in P}

df = pd.read_csv(DATA)
df["tm2_filled"] = df["tm2_c"].fillna(df.groupby("round")["tm2_c"].transform("median"))
df.loc[df["tm2_c"].isna(), "tm2_filled"] = df["tm2_filled"].fillna(df["tm2_filled"].median())
for c in COLS:
    if c == "tm2_c":
        continue
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["tm2_c"] = df["tm2_filled"]


def zs(v):
    v = np.asarray(v, float)
    return (v - v.mean()) / (v.std() + 1e-12)


print("=" * 74)
print("1) 单参数与本轮综合非特异性的秩相关（轮内，正号 = 越大越差）")
print("=" * 74)
print(f"{'参数':<14}{'r_R1':>9}{'r_R2':>9}{'pooled':>9}{'物理方向':>10}")
for c, cn, sg in P:
    rs = []
    for r in (1, 2):
        d = df[df["round"] == r]
        rs.append(spearmanr(d[c], d["ns_post_ft"]).correlation)
    rp = spearmanr(df[c], df["ns_post_ft"]).correlation
    exp = "越小越好" if sg < 0 else "越大越好"
    flag = "  <-- 与物理方向冲突" if (rs[0] * sg < 0 and rs[1] * sg < 0) else ""
    print(f"{cn:<14}{rs[0]:>+9.2f}{rs[1]:>+9.2f}{rp:>+9.2f}{exp:>10}{flag}")

# 轮内标准分
Z = {}
for c, _, _ in P:
    Z[c] = np.zeros(len(df))
for r in (1, 2):
    m = (df["round"] == r).values
    for c, _, _ in P:
        Z[c][m] = zs(df.loc[m, c].values)
Zdf = pd.DataFrame(Z)
y = (1 - df.groupby("round")["ns_post_ft"].rank(pct=True)).values  # 越大越好
R1 = (df["round"] == 1).values
R2 = (df["round"] == 2).values


def evalscore(s, label, verbose=False, quiet=False):
    rho = [spearmanr(s[R1], y[R1]).correlation, spearmanr(s[R2], y[R2]).correlation]
    ns = df["ns_post_ft"].values
    top = []
    for m in (R1, R2):
        top.append(len(set(np.argsort(-s[m])[:3]) & set(np.argsort(ns[m])[:3])) / 3)
    print(f"{label:<46} rho={rho[0]:+.2f}/{rho[1]:+.2f} (avg {np.mean(rho):+.2f})  Top3={top[0]*100:.0f}%/{top[1]*100:.0f}%")
    if verbose:
        for r, m in ((1, R1), (2, R2)):
            d = df.loc[m].assign(s=s[m]).sort_values("s", ascending=False)
            print(f"   第{r}轮: " + " > ".join(f"{r_.buffer}({int(r_.ns_post_ft)})" for _, r_ in d.iterrows()))
    return rho, top


print()
print("=" * 74)
print("2) 带符号约束的权重求解（NNLS，逐轮内标准分回归到排序分）")
print("=" * 74)
X = np.column_stack([Zdf[c].values * SIGN[c] for c in COLS])  # 方向归一：越大 = 越好


def loo_nnls(Xm, ym, alpha=1.0):
    pred = np.zeros(len(ym))
    for i in range(len(ym)):
        m = np.ones(len(ym), bool)
        m[i] = False
        # 岭项增强小样本稳定性
        A = np.vstack([Xm[m], np.sqrt(alpha) * np.eye(Xm.shape[1])])
        b = np.concatenate([ym[m], np.zeros(Xm.shape[1])])
        w, _ = nnls(A, b)
        pred[i] = Xm[i] @ w
    return pred


pred8 = loo_nnls(X, y)
evalscore(pred8, "NNLS 8 参数（LOO）")
# 全量权重
A = np.vstack([X, np.sqrt(1.0) * np.eye(8)])
b = np.concatenate([y, np.zeros(8)])
w8, _ = nnls(A, b)
w8n = w8 / w8.sum() if w8.sum() > 0 else w8
print("   全量归一权重:", {P[i][1]: round(float(w8n[i]), 3) for i in range(8)})

print()
print("=" * 74)
print("3) 对比：去掉 Tm2 / 去掉弱参数后的表现")
print("=" * 74)
for drop in [[], ["tm2_c"], ["tm2_c", "t_scattering_c"], ["tm2_c", "t_scattering_c", "t_size_c"]]:
    keep = [c for c in COLS if c not in drop]
    idx = [COLS.index(c) for c in keep]
    pr = loo_nnls(X[:, idx], y)
    nm = "保留 " + "/".join(P[i][1] for i in idx) if drop else "全部 8 个"
    evalscore(pr, f"{nm}")

print()
print("=" * 74)
print("3b) B 维度成分消融（固定 A 0.80 + 规则层）")
print("=" * 74)
A_grp = -0.55 * Zdf["radius_nm"].values - 0.45 * Zdf["pdi"].values
prot = df["buffer"].str.contains("蔗糖|海藻糖|山梨醇").values
phos = df["buffer"].str.contains("PBS|磷酸").values
ABL = {
    "B 仅 Tm1+Tonset+Tturb（5 参数模型）": {"tm1_c": .45, "tonset_c": .33, "t_turbidity_c": .22},    "B 加 Tm2（6 参数）": {"tm1_c": .38, "tm2_c": .14, "tonset_c": .28, "t_turbidity_c": .20},
    "B 加 Tscat（6 参数）": {"tm1_c": .38, "tonset_c": .28, "t_turbidity_c": .18, "t_scattering_c": .16},
    "B 加 Tsize（6 参数）": {"tm1_c": .38, "tonset_c": .28, "t_turbidity_c": .18, "t_size_c": .16},
    "B 全 6 项（8 参数模型）": {"tm1_c": .26, "tm2_c": .10, "tonset_c": .24, "t_turbidity_c": .18,
                        "t_scattering_c": .12, "t_size_c": .10},
}
for name, bw in ABL.items():
    tot = sum(bw.values())
    Bx = sum(w / tot * Zdf[c].values for c, w in bw.items())
    base = 0.80 * A_grp + 0.20 * Bx
    s = np.where(prot, base * 0.10 + 1.5, base) + np.where(phos, -3.0, 0)
    evalscore(s, name)

print()
print("=" * 74)
print("4) 结构化的两组权重（A 表面/胶体 vs B 构象稳定性），网格搜索 A 占比")
print("=" * 74)
A_grp = -0.55 * Zdf["radius_nm"].values - 0.45 * Zdf["pdi"].values
B_FIX = (
    0.26 * Zdf["tm1_c"].values + 0.10 * Zdf["tm2_c"].values
    + 0.24 * Zdf["tonset_c"].values + 0.18 * Zdf["t_turbidity_c"].values
    + 0.12 * Zdf["t_scattering_c"].values + 0.10 * Zdf["t_size_c"].values
)
for wa in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 1.0]:
    evalscore(wa * A_grp + (1 - wa) * B_FIX, f"综合 = {wa:.2f}*A + {1-wa:.2f}*B")

print()
print("=" * 74)
print("5) 加配方规则层（磷酸盐罚分 / 渗透保护剂）")
print("=" * 74)
prot = df["buffer"].str.contains("蔗糖|海藻糖|山梨醇").values
phos = df["buffer"].str.contains("PBS|磷酸").values
best = None
for wa in [0.6, 0.7, 0.8, 0.9, 1.0]:
    for ex, sb, pen in [(1.0, 0.0, 0.0), (0.10, 1.5, 3.0), (0.05, 1.8, 3.0), (0.0, 2.0, 3.0)]:
        base = wa * A_grp + (1 - wa) * B_FIX
        s = np.where(prot, base * ex + sb, base) + np.where(phos, -pen, 0)
        rho, top = evalscore(s, f"wa={wa:.2f} 保护剂(ex={ex},+{sb}) 磷酸盐-{pen}")
        if best is None or np.mean(rho) > best[0]:
            best = (np.mean(rho), wa, ex, sb, pen, rho, top)

print()
print("最佳: 平均 rho=%.2f  wa=%.2f ex=%.2f bonus=%.2f pen=%.1f  (%+.2f/%+.2f) Top3 %.0f%%/%.0f%%"
      % (best[0], best[1], best[2], best[3], best[4], best[5][0], best[5][1], best[6][0] * 100, best[6][1] * 100))

# 导出
wa, ex, sb, pen = best[1], best[2], best[3], best[4]
BW = {"tm1_c": 0.26, "tm2_c": 0.10, "tonset_c": 0.24, "t_turbidity_c": 0.18,
      "t_scattering_c": 0.12, "t_size_c": 0.10}
AW = {"radius_nm": 0.55, "pdi": 0.45}
out = {
    "params": [{"key": c, "cn": cn, "sign": sg, "group": "A" if c in AW else "B"} for c, cn, sg in P],
    "A_weights": AW, "B_weights": BW, "blend_A": wa,
    "rules": {"protectant_exempt": ex, "protectant_bonus": sb, "phosphate_penalty": pen},
    "perf": {"rho": best[5], "avg_rho": best[0], "top3": best[6]},
    "nnls_weights": {P[i][1]: round(float(w8n[i]), 4) for i in range(8)},
    "n": len(df),
    "samples": [
        {"id": r["sample_id"], "buffer": r["buffer"], "round": int(r["round"]),
         "ns": int(r["ns_post_ft"]),
         "v": [round(float(r[c]), 4) for c in COLS]}
        for _, r in df.iterrows()
    ],
    "tm2_missing": [r["sample_id"] for _, r in df.iterrows() if pd.isna(r["tm2_c"])],
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n导出:", OUT)
