/* ==========================================================================
   工具注册表
   --------------------------------------------------------------------------
   新增一个工具：
     1) 复制 tools/_template.html 为 tools/<id>.html，写好页面
     2) 在下面 TOOLS 数组里加一条记录
     3) 首页无需改动，卡片自动出现
   icon: flask | chart | book | sliders | grid | calc | clock
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
    desc: "用 Panta 的 8 项检测参数给候选 buffer 打分排序，输出前 3–4 个进入冻融实测。数据可从 Excel 直接粘贴。",
    href: "tools/buffer-screening.html",
    icon: "flask",
    status: "live",
    tags: ["8 参数", "打分排序", "Excel 粘贴"]
  }
];

const DOCS = [
  { t: "模型参数", d: "权重、规则层参数与验证指标", href: "model/eight_param_model.json" }
];

/* ---------- 渲染 ---------- */
(function () {
  const grid = document.getElementById("gridLive");
  if (!grid) return;

  const icon = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ICONS.grid}</svg>`;
  const arrow = `<span class="arw"><svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>`;
  const badge = s => s === "beta" ? `<span class="badge beta">试用</span>`
                    : s === "soon" ? `<span class="badge soon">规划中</span>` : "";

  grid.innerHTML = TOOLS.map(t => `
    <a class="row" href="${t.href}">
      <span class="ic">${icon(t.icon)}</span>
      <span class="bd">
        <span class="nm">${t.name}${badge(t.status)}</span>
        <span class="ds">${t.desc}</span>
      </span>
      <span class="tags">${(t.tags || []).map(x => `<span>${x}</span>`).join("")}</span>
      ${arrow}
    </a>`).join("");

  const cnt = document.getElementById("cntLive");
  if (cnt) cnt.textContent = TOOLS.length + " 个";

  const docBox = document.getElementById("docList");
  if (docBox) {
    docBox.innerHTML = DOCS.map(d =>
      `<a href="${d.href}">${d.t}<span>${d.d}</span></a>`).join("");
  }
})();
