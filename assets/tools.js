/* ==========================================================================
   工具注册表
   --------------------------------------------------------------------------
   新增一个工具只需三步：
     1) 把页面放到 tools/<id>.html（页面内返回条见 tools/buffer-screening.html 顶部）
     2) 在下面 TOOLS 数组里加一条记录
     3) 首页无需改动，卡片会自动出现
   status: "live" 可用 | "beta" 试用 | "soon" 规划中（soon 不可点击，href 留空）
   icon:   flask | chart | book | sliders | grid | calc | clock
   ========================================================================== */

const ICONS = {
  flask:  '<path d="M9 3h6M10 3v6.2L4.9 18a2 2 0 0 0 1.7 3h10.8a2 2 0 0 0 1.7-3L14 9.2V3"/><path d="M7.2 14h9.6"/>',
  chart:  '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16v-4"/><path d="M12.5 16V8"/><path d="M17 16v-6"/>',
  book:   '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H19v16H5.5A1.5 1.5 0 0 1 4 18.5z"/><path d="M8 4v16"/>',
  sliders:'<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  grid:   '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  calc:   '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8.5 7.5h7"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01M8.5 16h.01M12 16h.01M15.5 16h.01"/>',
  clock:  '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>'
};

const TOOLS = [
  {
    id: "buffer-screening",
    name: "Buffer 快速筛选",
    desc: "8 项 Panta 检测参数按锁定方向加权打分，对候选 buffer 排序，挑出前 3–4 个进入冻融实测。支持 Excel 一键粘贴。",
    href: "tools/buffer-screening.html",
    icon: "flask",
    status: "live",
    tags: ["Panta 8 参数", "排序打分", "Excel 导入"]
  },
  {
    id: "ns-trend",
    name: "非特异性趋势看板",
    desc: "把多轮实测非特异性按配方、批号、冻融次数汇总成趋势线，看配方改进是否真的落地。",
    href: "",
    icon: "chart",
    status: "soon",
    tags: ["多轮数据", "趋势对比"]
  },
  {
    id: "param-explorer",
    name: "参数相关性探索",
    desc: "8 个参数与实测值之间的散点、秩相关与共线性诊断，用于判断哪一维真正带信息量。",
    href: "",
    icon: "sliders",
    status: "soon",
    tags: ["相关性", "消融分析"]
  },
  {
    id: "buffer-calc",
    name: "配方浓度换算",
    desc: "母液体积、终浓度、盐浓度与渗透压估算，减少配液时的手算与换算失误。",
    href: "",
    icon: "calc",
    status: "soon",
    tags: ["配液", "单位换算"]
  }
];

const DOCS = [
  { t: "分析报告", d: "权重依据、验证方法与能力边界", href: "分析报告.md" },
  { t: "标定数据", d: "两轮筛选 23 个样本的完整参数表", href: "data/buffer_screening.csv" },
  { t: "模型参数", d: "权重、规则层参数与验证指标（JSON）", href: "model/eight_param_model.json" }
];

/* ---------- 渲染 ---------- */
(function () {
  const liveGrid = document.getElementById("gridLive");
  const soonGrid = document.getElementById("gridSoon");
  if (!liveGrid) return;

  const STATUS = { live: "可用", beta: "试用", soon: "规划中" };

  const iconSVG = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ICONS.grid}</svg>`;
  const arrow = `<span class="arw"><svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>`;

  function card(t) {
    const inner = `
      <div class="ic">${iconSVG(t.icon)}</div>
      <div class="bd">
        <div class="nm">${t.name}<span class="badge ${t.status}">${STATUS[t.status] || ""}</span></div>
        <div class="ds">${t.desc}</div>
        <div class="tags">${(t.tags || []).map(x => `<span>${x}</span>`).join("")}</div>
      </div>
      ${t.status === "soon" ? "" : arrow}`;

    return t.status === "soon" || !t.href
      ? `<div class="tool soon" data-k="${(t.name + t.desc + (t.tags || []).join("")).toLowerCase()}">${inner}</div>`
      : `<a class="tool" href="${t.href}" data-k="${(t.name + t.desc + (t.tags || []).join("")).toLowerCase()}">${inner}</a>`;
  }

  function render(list) {
    const live = list.filter(t => t.status !== "soon");
    const soon = list.filter(t => t.status === "soon");
    liveGrid.innerHTML = live.map(card).join("");
    soonGrid.innerHTML = soon.map(card).join("");
    document.getElementById("cntLive").textContent = live.length + " 个";
    const topCnt = document.getElementById("cntS1");
    if (topCnt) topCnt.textContent = live.length;
    document.getElementById("cntSoon").textContent = soon.length + " 个";
    document.getElementById("sectSoon").style.display = soon.length ? "" : "none";
    document.getElementById("gridLive").style.display = live.length ? "" : "none";
    document.getElementById("sectLive").style.display = live.length ? "" : "none";
    document.getElementById("noResult").style.display = list.length ? "none" : "";
  }

  render(TOOLS);

  // 文档
  const docBox = document.getElementById("docList");
  if (docBox) {
    docBox.innerHTML = DOCS.map(d =>
      `<a class="doc" href="${d.href}"><div class="t">${d.t}</div><div class="d">${d.d}</div></a>`).join("");
  }

  // 搜索
  const input = document.getElementById("q");
  if (input) {
    const apply = () => {
      const q = input.value.trim().toLowerCase();
      document.getElementById("clr").style.display = q ? "" : "none";
      render(q ? TOOLS.filter(t =>
        (t.name + t.desc + (t.tags || []).join("")).toLowerCase().includes(q)) : TOOLS);
    };
    input.addEventListener("input", apply);
    document.getElementById("clr").addEventListener("click", () => { input.value = ""; apply(); input.focus(); });
    document.addEventListener("keydown", e => {
      if (e.key === "/" && document.activeElement !== input) { e.preventDefault(); input.focus(); }
      if (e.key === "Escape" && document.activeElement === input) { input.value = ""; apply(); input.blur(); }
    });
    apply();
  }
})();
