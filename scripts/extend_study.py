# -*- coding: utf-8 -*-
"""
表面性质指标 · 接入前验证（bridge study）

用途：
  1) 检查扩展数据表的缺失情况，告诉你还差哪些数据；
  2) 有数据后，逐项评估「单因子排序能力 + 与现有 8 参数模型的正交性 + 增量贡献」；
  3) 按写死的三条判据给出「进权重 / 进红旗规则 / 弃用」的结论。

判据（不随结果调整，防止事后择优）：
  C1 单因子 |Spearman ρ| >= 0.45，且两批（或两轮）符号一致
  C2 与现有 8 参数综合分的相关 |r| < 0.60（否则没有正交信息，加了也白加）
  C3 加入后留一法 ρ 提升 >= 0.05，且没有任何一批下降 > 0.10

运行：python scripts/extend_study.py [可选的 CSV 路径]
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 \
       else BASE / "data" / "buffer_screening_extended.csv"

# 现有 8 参数权重（model/eight_param_model.json）
P8 = {
    "radius_nm": (-1, 0.44),
    "pdi": (-1, 0.36),
    "tm1_c": (+1, 0.060),
    "tm2_c": (+1, 0.036),
    "tonset_c": (+1, 0.048),
    "t_turbidity_c": (+1, 0.032),
    "t_scattering_c": (+1, 0.012),
    "t_size_c": (+1, 0.012),
}
BLEND_A = 0.80
RULES = dict(protectant_exempt=0.10, protectant_bonus=1.50, phosphate_penalty=3.0)

# 新增指标：key -> (中文名, 方向 +1 越大越好 / -1 越小越好, 单位, 判据阈值说明)
NEW = {
    "hic_rrt": ("HIC 相对保留", -1, "—", "> 1.20 视为高疏水"),
    "zeta_mv": ("ζ 电位", +1, "mV", "|ζ| < 5 mV 高危"),
    "sec_mono_pct": ("SEC 单体%", +1, "%", "< 95% 淘汰"),
    "dls_kcps_norm": ("DLS 归一计数率", -1, "kcps/(mg·mL⁻¹)", "> 2× 均值 标记"),
}


def zscore(v):
    v = np.asarray(v, float)
    sd = v.std()
    return (v - v.mean()) / (sd if sd > 1e-12 else 1.0)


def legacy_score(df):
    """复算现有 8 参数模型（含规则层），返回 0-100 分与每行分值。"""
    d = df.copy()
    # Tm2 缺失用本轮中位数填补
    d["tm2_c"] = d.groupby("round")["tm2_c"].transform(lambda s: s.fillna(s.median()))
    Z = {}
    for f in P8:
        Z[f] = np.zeros(len(d))
        for r, idx in d.groupby("round").groups.items():
            s = d.loc[idx, f].astype(float).values
            Z[f][d.index.get_indexer(idx)] = zscore(s)
    A = sum(sg * w * Z[f] for f, (sg, w) in P8.items() if f in ("radius_nm", "pdi")) / 0.80
    B = sum(sg * w * Z[f] for f, (sg, w) in P8.items() if f not in ("radius_nm", "pdi")) / 0.20
    base = BLEND_A * A + (1 - BLEND_A) * B
    prot = d["buffer"].str.contains("蔗糖|海藻糖|山梨醇", regex=True).values
    phos = d["buffer"].str.contains("PBS|磷酸", regex=True).values
    s = np.where(prot, base * RULES["protectant_exempt"] + RULES["protectant_bonus"], base)
    s = s + np.where(phos, -RULES["phosphate_penalty"], 0.0)
    return s


def loo_rho(X, y, groups, ridge=3.0):
    """带岭项的留一法排序相关（无截距的非负最小二乘近似用 lstsq 代替）。"""
    from sklearn.linear_model import Ridge

    pred = np.zeros(len(y))
    for i in range(len(y)):
        m = np.ones(len(y), bool)
        m[i] = False
        pred[i] = Ridge(alpha=ridge).fit(X[m], y[m]).predict(X[i:i + 1])[0]
    out = []
    for g in pd.unique(groups):
        m = groups == g
        out.append(spearmanr(pred[m], y[m]).correlation if m.sum() >= 5 else np.nan)
    return np.array(out, float)


def main():
    df = pd.read_csv(DATA, encoding="utf-8-sig")
    n = len(df)
    print("=" * 78)
    print(f"扩展数据表：{DATA.name}   n={n}")
    print("=" * 78)

    missing = [k for k in NEW if k not in df.columns or df[k].notna().sum() == 0]
    if missing:
        print("\n[待测] 以下指标尚无数据：")
        for k in missing:
            cn, sg, unit, note = NEW[k]
            print(f"  · {cn:<16} 方向 {'↑' if sg > 0 else '↓'}  {note}")
        print(f"\n建议首批测定 {min(10, n)} 个样本（覆盖最优/中/高危三个档位），"
              f"每个指标至少 8 个有效值才能判断方向。")
        print("填好 data/buffer_screening_extended.csv 后重跑本脚本即可得到纳入结论。")

    y_raw = df["ns_post_ft"].astype(float)
    # 目标：批内秩（1 = 最差），避免批次绝对值差异
    y = (1 - df.groupby("round")["ns_post_ft"].rank(pct=True)).values
    groups = df["round"].values

    s0 = legacy_score(df)
    rho0 = [spearmanr(s0[groups == g], y[groups == g]).correlation
            for g in pd.unique(groups)]
    print(f"\n基准（现有 8 参数）批内 ρ：" + " / ".join(f"{r:+.2f}" for r in rho0)
          + f"   平均 {np.nanmean(rho0):+.2f}")

    ready = [k for k in NEW if k in df.columns and df[k].notna().sum() >= 8]
    if not ready:
        print("\n暂无可评估的新指标，先补数据。")
        return

    print("\n" + "=" * 78)
    print("逐项评估")
    print("=" * 78)
    verdict = {}
    for k in ready:
        cn, sg, unit, _ = NEW[k]
        v = df[k].astype(float)
        ok = v.notna().values
        vv = v.fillna(v.median()).values

        # C1 单因子
        per = [spearmanr(vv[(groups == g) & ok], y[(groups == g) & ok]).correlation
               if ((groups == g) & ok).sum() >= 5 else np.nan for g in pd.unique(groups)]
        sign_ok = all(np.sign(p) == sg for p in per if not np.isnan(p))
        c1 = (abs(np.nanmean(per)) >= 0.45) and sign_ok

        # C2 正交性
        r_leg = np.corrcoef(vv[ok], s0[ok])[0, 1]
        c2 = abs(r_leg) < 0.60

        # C3 增量
        X0 = np.column_stack([s0])
        X1 = np.column_stack([s0, sg * zscore(vv)])
        p0 = loo_rho(X0, y, groups)
        p1 = loo_rho(X1, y, groups)
        d = p1 - p0
        c3 = (np.nanmean(d) >= 0.05) and (np.nanmin(d) > -0.10)

        if c1 and c2 and c3:
            vd = "进权重"
        elif c1 and c2:
            vd = "进红旗规则"
        else:
            vd = "弃用"
        verdict[k] = vd

        print(f"\n{cn}（{k}，{unit}）")
        print(f"  单因子批内 ρ      : " + " / ".join(f"{p:+.2f}" for p in per)
              + f"   方向{'一致' if sign_ok else '不一致⚠'}")
        tag_orth = "正交" if abs(r_leg) < 0.6 else "信息重叠"
        print(f"  与现有综合分相关  : {r_leg:+.2f}（{tag_orth}）")
        print(f"  留一 ρ 基准→加入  : " + "→".join(f"{a:+.2f}" for a in [np.nanmean(p0), np.nanmean(p1)])
              + f"  Δ={np.nanmean(d):+.2f}")
        print(f"  判据 C1{'✓' if c1 else '✗'} C2{'✓' if c2 else '✗'} C3{'✓' if c3 else '✗'}"
              f"  → 结论：{vd}")

    print("\n" + "=" * 78)
    print("汇总：" + "；".join(f"{NEW[k][0]}={v}" for k, v in verdict.items()))
    print("=" * 78)

    out = BASE / "model" / "extend_study.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "n": int(n),
        "baseline_rho": [float(x) for x in rho0],
        "criteria": {"C1_rho": 0.45, "C2_orthogonality": 0.60, "C3_delta": 0.05},
        "verdict": verdict,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结论已写入 {out.relative_to(BASE)}")


if __name__ == "__main__":
    main()
