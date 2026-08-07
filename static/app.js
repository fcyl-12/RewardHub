const appState = {
  data: null,
  accounts: [],
  page: "home",
  selectedDate: localDate(),
  historyYear: new Date().getFullYear(),
  historyMonth: new Date().getMonth(),
  editorKind: null,
  editorId: null,
  selectedIcon: null,
  accountEditId: null,
};

const CUSTOM_IMAGES = {
  "child-boy": { src: "/custom-assets/child-boy", fallback: "/static/avatars/boy.svg" },
  "child-girl": { src: "/custom-assets/child-girl", fallback: "/static/avatars/girl.svg" },
  "adult-male": { src: "/custom-assets/adult-male", fallback: "/static/avatars/adult-male.svg" },
  "adult-female": { src: "/custom-assets/adult-female", fallback: "/static/avatars/adult-female.svg" },
  "account-log": { src: "/custom-assets/account-log", fallback: "/static/illustrations/children-pair.svg" },
  "login-cover": { src: "/custom-assets/login-cover", fallback: "/static/illustrations/children-pair.svg" },
  "control-center": { src: "/static/custom/app-icon.png", fallback: "/static/illustrations/children-logo.svg" },
};
const AVATARS = {
  boy: { label: "男孩头像", ...CUSTOM_IMAGES["child-boy"], role: "child" },
  girl: { label: "女孩头像", ...CUSTOM_IMAGES["child-girl"], role: "child" },
  "adult-male": { label: "爸爸头像", ...CUSTOM_IMAGES["adult-male"], role: "admin" },
  "adult-female": { label: "妈妈头像", ...CUSTOM_IMAGES["adult-female"], role: "admin" },
};
const PROJECT_ICONS = [
  ["points.svg", "积分"], ["homework.svg", "作业"], ["book.svg", "阅读"],
  ["chore.svg", "家务"], ["sport.svg", "运动"], ["bedtime.svg", "早睡"],
  ["television.svg", "电视"], ["game.svg", "游戏"], ["snack.svg", "零食"],
  ["outing.svg", "外出"], ["gift.svg", "奖励"], ["warning.svg", "提醒"],
];
const DEFAULT_ITEM_ICONS = { earn: "points.svg", deduct: "warning.svg", reward: "gift.svg" };
const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const monthNames = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

function localDate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}

function avatarSource(value) {
  return AVATARS[value]?.src || AVATARS.boy.src;
}

function avatarFallback(value) {
  return AVATARS[value]?.fallback || AVATARS.boy.fallback;
}

function setImageSource(element, source, fallback) {
  if (!element) return;
  element.onerror = () => {
    element.onerror = null;
    if (fallback) element.src = fallback;
  };
  element.src = source;
}

function avatarImage(value, className = "avatar avatar-small", alt = "") {
  return `<img class="${className}" src="${avatarSource(value)}" alt="${escapeHtml(alt)}" onerror="this.onerror=null;this.src='${avatarFallback(value)}'">`;
}

function illustrationSource(icon, kind = "earn") {
  const known = PROJECT_ICONS.some(([file]) => file === icon);
  const fallback = DEFAULT_ITEM_ICONS[kind === "exchange" ? "reward" : kind] || DEFAULT_ITEM_ICONS.earn;
  return `/static/illustrations/${known ? icon : fallback}`;
}

function itemIllustration(icon, kind) {
  return `<img class="project-visual" src="${illustrationSource(icon, kind)}" alt="">`;
}

function signed(value) {
  const number = Number(value) || 0;
  return number > 0 ? `+${number}` : String(number);
}

function displayDateTime(value) {
  return value ? String(value).replace("T", " ").slice(0, 16) : "暂无";
}

function recordsFor(date) {
  return (appState.data?.records || []).filter((record) => record.date === date);
}

function dayTotal(date) {
  return recordsFor(date).reduce((total, record) => total + Number(record.amount), 0);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || "请求失败");
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function loadState() {
  try {
    appState.data = await api("/api/state");
    if (appState.data.user?.role === "admin") {
      appState.accounts = (await api("/api/accounts")).accounts;
    } else {
      appState.accounts = [];
    }
    showApp();
    navigate(appState.page);
  } catch (error) {
    if (error.status === 401) showLogin();
    else showToast(error.message);
  }
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-header").classList.remove("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
  document.getElementById("bottom-nav").classList.remove("hidden");
  document.getElementById("connection-state").textContent = "数据库已连接";
}

function showLogin() {
  appState.data = null;
  appState.page = "home";
  closeModal();
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app-header").classList.add("hidden");
  document.getElementById("app-shell").classList.add("hidden");
  document.getElementById("bottom-nav").classList.add("hidden");
}

function updateAccountUi() {
  const user = appState.data?.user;
  const isAdmin = user?.role === "admin";
  document.body.dataset.role = isAdmin ? "admin" : "child";
  document.querySelectorAll(".admin-only").forEach((element) => element.classList.toggle("hidden", !isAdmin));
  document.querySelectorAll(".child-only").forEach((element) => element.classList.toggle("hidden", isAdmin));
  document.getElementById("account-label").textContent = user ? `${user.display_name} · ${isAdmin ? "管理账号" : "娃娃账号"}` : "";
  setImageSource(document.getElementById("user-avatar"), avatarSource(user?.avatar), avatarFallback(user?.avatar));
  document.getElementById("nav-requests-label").textContent = isAdmin ? "审核" : "申请";
  const selector = document.getElementById("child-select");
  const children = appState.data.children || [];
  if (isAdmin) {
    selector.classList.toggle("hidden", !children.length);
    selector.innerHTML = children.map((child) => `<option value="${child.id}">${escapeHtml(child.display_name)}</option>`).join("");
    selector.value = String(appState.data.active_child_id || "");
  } else {
    selector.classList.add("hidden");
  }
}

function navigate(page) {
  const isAdmin = appState.data?.user?.role === "admin";
  const adminPages = ["deduct", "accounts", "settings"];
  if (adminPages.includes(page) && !isAdmin) page = "home";
  appState.page = page;
  document.querySelectorAll(".page").forEach((element) => element.classList.toggle("active", element.dataset.page === page));
  document.querySelectorAll(".nav-button").forEach((element) => element.classList.toggle("active", element.dataset.pageTarget === page));
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function render() {
  if (!appState.data) return;
  updateAccountUi();
  renderHome();
  renderEarnLists();
  renderDeductList();
  renderExchangeList();
  renderManagement();
  renderRequests();
  renderAccounts();
  renderRecords();
}

function activeAccount() {
  if (appState.data?.active_child) return appState.data.active_child;
  return appState.data?.user?.role === "child" ? appState.data.user : {};
}

function renderHome() {
  const data = appState.data;
  const user = data.user;
  const account = activeAccount();
  const hasChild = Boolean(account.id);
  const today = localDate();
  const todayRecords = recordsFor(today);
  const income = todayRecords.filter((record) => record.type === "income").reduce((sum, record) => sum + Number(record.amount), 0);
  const expense = Math.abs(todayRecords.filter((record) => record.type === "expense").reduce((sum, record) => sum + Number(record.amount), 0));
  const children = (data.account_overview || []).filter((item) => item.role === "child");
  const pending = children.reduce((sum, item) => sum + Number(item.pending_count), 0);
  const weekTotal = dayNames.reduce((sum, _, index) => {
    const current = new Date();
    const day = current.getDay() || 7;
    current.setDate(current.getDate() - day + index + 1);
    return sum + dayTotal(localDate(current));
  }, 0);
  document.getElementById("home-title").textContent = user.role === "admin" ? (hasChild ? "家庭监控总控" : "先创建娃娃账号") : "我的积分空间";
  document.getElementById("home-subtitle").textContent = user.role === "admin" ? (hasChild ? "总览积分、审批和账户状态，快速执行家庭规则" : "当前还没有娃娃账号，请先到账号管理创建") : "完成任务后申请积分，等待家长审核到账";
  document.getElementById("today-label").textContent = today;
  setImageSource(
    document.getElementById("active-avatar"),
    account.avatar ? avatarSource(account.avatar) : CUSTOM_IMAGES["control-center"].src,
    account.avatar ? avatarFallback(account.avatar) : CUSTOM_IMAGES["control-center"].fallback,
  );
  document.getElementById("active-name").textContent = account.display_name || "暂无娃娃账号";
  document.getElementById("active-username").textContent = account.username ? `账号：${account.username}` : "";
  document.getElementById("active-account-kicker").textContent = user.role === "admin" ? "当前操作对象" : "我的账号";
  document.getElementById("total-points").textContent = Number(data.total_points || 0).toLocaleString("zh-CN");
  document.getElementById("earn-target-name").textContent = account.display_name || "暂无娃娃账号";
  document.getElementById("deduct-target-name").textContent = account.display_name || "暂无娃娃账号";
  document.getElementById("pending-action-label").textContent = `${pending} 条待处理`;
  document.querySelector(".hero-actions.admin-only")?.classList.toggle("hidden", user.role !== "admin" || !hasChild);
  document.getElementById("no-child-panel")?.classList.toggle("hidden", !(user.role === "admin" && !hasChild));
  const metrics = user.role === "admin" ? [
    ["娃娃账户", children.length, "个", "metric-green"],
    ["家庭总积分", children.reduce((sum, item) => sum + Number(item.total_points), 0), "分", "metric-blue"],
    ["待审核申请", pending, "条", pending ? "metric-orange" : "metric-green"],
    ["本周变化", signed(weekTotal), "分", weekTotal >= 0 ? "metric-green" : "metric-red"],
  ] : [
    ["今日赚取", income, "分", "metric-green"],
    ["今日扣除", expense, "分", "metric-red"],
    ["今日净增", signed(income - expense), "分", income >= expense ? "metric-blue" : "metric-orange"],
    ["待审核申请", (data.requests || []).filter((item) => item.status === "pending").length, "条", "metric-orange"],
  ];
  document.getElementById("home-metrics").innerHTML = metrics.map(([label, value, unit, color]) => `<div class="metric-card ${color}"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${unit}</small></div>`).join("");
  const controlTitle = document.getElementById("control-center-title");
  const controlSubtitle = document.getElementById("control-center-subtitle");
  const controlChildCount = document.getElementById("control-child-count");
  const controlTotalPoints = document.getElementById("control-total-points");
  const controlPendingCount = document.getElementById("control-pending-count");
  if (controlTitle) controlTitle.textContent = hasChild ? `${account.display_name} 的积分中枢` : "家庭积分中枢";
  if (controlSubtitle) controlSubtitle.textContent = hasChild ? `当前监控 ${account.username || "娃娃账号"}，可立即执行家庭规则` : "先创建娃娃账号，再开始家庭积分管理";
  if (controlChildCount) controlChildCount.textContent = children.length;
  if (controlTotalPoints) controlTotalPoints.textContent = children.reduce((sum, item) => sum + Number(item.total_points), 0).toLocaleString("zh-CN");
  if (controlPendingCount) controlPendingCount.textContent = pending;
  const homeSummary = document.getElementById("home-account-summary");
  if (homeSummary) {
    homeSummary.innerHTML = children.length ? children.map((child) => `<tr><td><div class="table-person">${avatarImage(child.avatar, "avatar avatar-table", child.display_name)}<div><strong>${escapeHtml(child.display_name)}</strong><small>${escapeHtml(child.username)}</small></div></div></td><td class="table-number">${Number(child.total_points).toLocaleString("zh-CN")}</td><td class="table-number ${Number(child.today_net) >= 0 ? "income" : "expense"}">${signed(child.today_net)}</td><td><span class="pending-badge">${Number(child.pending_count)}</span></td><td><span class="status-pill ${Number(child.pending_count) ? "status-pending" : "status-approved"}">${Number(child.pending_count) ? "待审核" : "运行正常"}</span></td></tr>`).join("") : `<tr><td colspan="5"><div class="empty-state">暂无娃娃账号，请先创建账号</div></td></tr>`;
  }
  renderWeekGrid(document.getElementById("home-week-grid"), "home-week-title");
  const preview = document.getElementById("home-request-preview");
  const recent = (data.requests || []).slice(0, 3);
  preview.innerHTML = recent.length ? recent.map(requestMarkup).join("") : `<div class="empty-state">暂无申请记录</div>`;
}

function renderEarnLists() {
  renderItemList(document.getElementById("earn-list"), appState.data.earn_items || [], "earn", "admin");
  renderItemList(document.getElementById("child-earn-list"), appState.data.earn_items || [], "earn", "child");
}

function renderDeductList() {
  renderItemList(document.getElementById("deduct-list"), appState.data.deduct_items || [], "deduct", "admin");
}

function renderExchangeList() {
  renderItemList(document.getElementById("exchange-list"), appState.data.rewards || [], "exchange", "child");
}

function renderItemList(container, items, kind, mode) {
  if (!container) return;
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">暂无项目，请先在项目设置中添加。</div>`;
    return;
  }
  const isExchange = kind === "exchange";
  const actionText = isExchange ? "申请兑换" : mode === "child" ? "申请" : kind === "earn" ? "加分" : "扣分";
  const actionClass = kind === "deduct" ? "button-danger" : isExchange ? "button-dark" : "button-primary";
  const pointSign = kind === "deduct" || isExchange ? "-" : "+";
    container.innerHTML = items.map((item) => `<div class="list-row"><div class="item-info"><div class="project-visual-wrap">${itemIllustration(item.icon, kind)}</div><div><strong>${escapeHtml(item.name)}</strong><span class="item-points ${kind === "deduct" || isExchange ? "expense" : "income"}">${pointSign}${Math.abs(Number(item.points))} 积分</span></div></div><button class="button button-small ${actionClass}" data-action="${kind}" data-id="${item.id}" type="button">${actionText}</button></div>`).join("");
}

function renderManagement() {
  renderManageList("earn-manage-list", appState.data.earn_items || [], "earn");
  renderManageList("deduct-manage-list", appState.data.deduct_items || [], "deduct");
  renderManageList("reward-manage-list", appState.data.rewards || [], "reward");
}

function renderManageList(elementId, items, kind) {
  const container = document.getElementById(elementId);
  if (!container) return;
  const isExpense = kind === "deduct" || kind === "reward";
  container.innerHTML = items.length ? items.map((item) => `<div class="list-row"><div class="item-info"><div class="project-visual-wrap">${itemIllustration(item.icon, kind)}</div><div><strong>${escapeHtml(item.name)}</strong><span class="item-points ${isExpense ? "expense" : "income"}">${isExpense ? "-" : "+"}${Math.abs(Number(item.points))} 积分</span></div></div><div class="row-actions"><button class="button button-small button-outline" data-action="edit" data-kind="${kind}" data-id="${item.id}" type="button">编辑</button><button class="button button-small button-outline-danger" data-action="delete" data-kind="${kind}" data-id="${item.id}" type="button">删除</button></div></div>`).join("") : `<div class="empty-state">暂无项目</div>`;
}

function requestMarkup(request) {
  const statusText = { pending: "待审核", approved: "已通过", rejected: "已拒绝" };
  const kindText = { earn: "赚取申请", exchange: "兑换申请", deduct: "扣分申请", manual: "补录申请" };
  const status = request.status || "pending";
  const childAvatar = request.child_avatar || "boy";
  const action = appState.data.user.role === "admin" && status === "pending" ? `<div class="row-actions"><button class="button button-small button-primary" data-action="approve-request" data-id="${request.id}" type="button">通过</button><button class="button button-small button-outline-danger" data-action="reject-request" data-id="${request.id}" type="button">拒绝</button></div>` : `<span class="status-pill status-${status}">${statusText[status] || status}</span>`;
  return `<div class="request-row"><div class="request-person">${avatarImage(childAvatar, "avatar avatar-small", request.child_name || "娃娃")}<div><strong>${escapeHtml(kindText[request.kind] || "积分申请")}：${escapeHtml(request.title)}</strong><span>${appState.data.user.role === "admin" ? `${escapeHtml(request.child_name || "娃娃")} · ` : ""}${escapeHtml(request.date)} ${escapeHtml(request.time)}</span>${status === "rejected" && request.reject_reason ? `<em>${escapeHtml(request.reject_reason)}</em>` : ""}</div></div><strong class="request-amount ${Number(request.amount) >= 0 ? "income" : "expense"}">${signed(request.amount)} 分</strong>${action}</div>`;
}

function renderRequests() {
  const isAdmin = appState.data.user.role === "admin";
  document.getElementById("requests-title").textContent = isAdmin ? "审核申请" : "我的申请";
  document.getElementById("requests-subtitle").textContent = isAdmin ? "娃娃提交的赚分或兑换申请，审核后才会更新余额。" : "申请不会直接改变余额，等待管理账号审核。";
  const requests = appState.data.requests || [];
  document.getElementById("requests-list").innerHTML = requests.length ? requests.map(requestMarkup).join("") : `<div class="empty-state">暂无申请记录</div>`;
}

function renderAccounts() {
  const summaryBody = document.getElementById("account-summary-body");
  const logBody = document.getElementById("account-log-body");
  if (!summaryBody || !logBody || appState.data.user.role !== "admin") return;
  const currentId = Number(appState.data.user.id);
  const overview = appState.data.account_overview || [];
  summaryBody.innerHTML = overview.length ? overview.map((account) => {
    const isChild = account.role === "child";
    const deleteButton = Number(account.id) === currentId ? "" : `<button class="button button-small button-outline-danger" data-action="delete-account" data-id="${account.id}" type="button">删除</button>`;
    const action = `<div class="row-actions"><button class="button button-small button-outline" data-action="edit-account" data-id="${account.id}" type="button">编辑</button>${deleteButton}</div>`;
    return `<tr><td><div class="table-person">${avatarImage(account.avatar, "avatar avatar-table", account.display_name)}<div><strong>${escapeHtml(account.display_name)}</strong><small>${escapeHtml(account.avatar === "girl" ? "女孩头像" : account.avatar === "boy" ? "男孩头像" : "管理头像")}</small></div></div></td><td>${escapeHtml(account.username)}</td><td>${isChild ? "娃娃账号" : "管理账号"}</td><td class="table-number">${Number(account.total_points).toLocaleString("zh-CN")}</td><td class="table-number ${Number(account.today_net) >= 0 ? "income" : "expense"}">${signed(account.today_net)}</td><td><span class="pending-badge">${Number(account.pending_count)}</span></td><td>${action}</td></tr>`;
  }).join("") : `<tr><td colspan="7"><div class="empty-state">暂无账号</div></td></tr>`;
  const actionText = { create_child: "新增娃娃", create_admin: "新增管理", update_child: "修改娃娃资料", update_admin: "修改管理资料", delete_child: "删除娃娃", delete_admin: "删除管理" };
  logBody.innerHTML = (appState.data.account_logs || []).length ? appState.data.account_logs.map((log) => `<tr><td>${displayDateTime(log.created_at)}</td><td><div class="table-person">${avatarImage(log.actor_avatar, "avatar avatar-table", log.actor_name)}<strong>${escapeHtml(log.actor_name)}</strong></div></td><td><span class="log-action ${log.target_role === "admin" ? "admin" : "child"}">${actionText[log.action] || escapeHtml(log.action)}</span></td><td><div class="table-person">${avatarImage(log.target_avatar, "avatar avatar-table", log.target_name)}<div><strong>${escapeHtml(log.target_name)}</strong><small>${escapeHtml(log.target_username)}</small></div></div></td><td>${log.target_role === "admin" ? "管理账号" : "娃娃账号"}</td></tr>`).join("") : `<tr><td colspan="5"><div class="empty-state">暂无账号变更记录</div></td></tr>`;
}

function renderWeekGrid(container, titleId) {
  if (!container) return;
  const monday = new Date();
  const day = monday.getDay() || 7;
  monday.setDate(monday.getDate() - day + 1);
  let total = 0;
  container.innerHTML = dayNames.map((dayName, index) => {
    const current = new Date(monday);
    current.setDate(monday.getDate() + index);
    const date = localDate(current);
    const amount = dayTotal(date);
    total += amount;
    return `<button class="day-item${date === localDate() ? " today" : ""}${date === appState.selectedDate ? " selected" : ""}" data-select-date="${date}" type="button"><span>${dayName}</span><strong>${signed(amount)}</strong></button>`;
  }).join("");
  const title = document.getElementById(titleId);
  if (title) title.textContent = `本周积分（${signed(total)}）`;
}

function renderRecords() {
  const weekGrid = document.getElementById("records-week-grid");
  if (!weekGrid) return;
  renderWeekGrid(weekGrid, "records-week-title");
  document.getElementById("selected-day-title").textContent = `${appState.selectedDate} 每日记录`;
  const records = recordsFor(appState.selectedDate);
  document.getElementById("day-records").innerHTML = records.length ? records.map((record) => `<div class="record-row"><div><strong>${escapeHtml(record.title)}</strong><span>${escapeHtml(record.time)}</span></div><strong class="record-amount ${record.type}">${signed(record.amount)}</strong>${appState.data.user.role === "admin" ? `<button class="button button-small button-outline-danger" data-action="undo" data-id="${record.id}" type="button">撤销</button>` : ""}</div>`).join("") : `<div class="empty-state">该日期暂无积分记录</div>`;
  renderHistory();
}

function renderHistory() {
  const year = appState.historyYear;
  const month = appState.historyMonth;
  document.getElementById("history-month-label").textContent = `${year}年${month + 1}月`;
  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startPadding = (first.getDay() || 7) - 1;
  const daily = new Map();
  (appState.data.records || []).forEach((record) => daily.set(record.date, (daily.get(record.date) || 0) + Number(record.amount)));
  let cells = Array.from({ length: startPadding }, () => `<div class="month-day empty"></div>`).join("");
  for (let day = 1; day <= daysInMonth; day += 1) {
    const value = daily.get(`${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`) || 0;
    cells += `<div class="month-day${day === new Date().getDate() && month === new Date().getMonth() && year === new Date().getFullYear() ? " today" : ""}"><span>${day}</span><strong>${value ? signed(value) : ""}</strong></div>`;
  }
  document.getElementById("history-calendar").innerHTML = `<div class="month-calendar"><div class="month-weekdays">${dayNames.map((name) => `<span>${name.slice(1)}</span>`).join("")}</div><div class="month-days">${cells}</div></div>`;
}

function openEditor(kind, id = null) {
  appState.editorKind = kind;
  appState.editorId = id;
  const item = id ? findItem(kind, id) : null;
  appState.selectedIcon = item?.icon || DEFAULT_ITEM_ICONS[kind];
  document.getElementById("modal-title").textContent = `${item ? "编辑" : "新增"}${kind === "earn" ? "加分项目" : kind === "reward" ? "兑换奖励" : "扣分项目"}`;
  document.getElementById("editor-name").value = item?.name || "";
  document.getElementById("editor-points").value = item ? Math.abs(Number(item.points)) : "";
  renderIconPicker();
  showModal("editor-form");
}

function renderIconPicker() {
  const container = document.getElementById("editor-icons");
  if (!container) return;
  container.innerHTML = PROJECT_ICONS.map(([file, label]) => `<button class="icon-choice${file === appState.selectedIcon ? " selected" : ""}" data-project-icon="${file}" type="button" title="${label}" aria-label="${label}"><img src="/static/illustrations/${file}" alt=""><span>${label}</span></button>`).join("");
  document.getElementById("editor-icon").value = appState.selectedIcon || "";
}

function openManual() {
  const form = document.getElementById("manual-form");
  form.reset();
  form.elements.date.value = appState.selectedDate || localDate();
  showModal("manual-form");
}

function fillAvatarOptions(role, selected = "") {
  const options = role === "admin" ? ["adult-male", "adult-female"] : ["boy", "girl"];
  document.getElementById("account-avatar").innerHTML = options.map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${AVATARS[value].label}</option>`).join("");
}

function openAccount() {
  appState.accountEditId = null;
  const form = document.getElementById("account-form");
  form.reset();
  document.getElementById("account-modal-title").textContent = "新增账号";
  document.getElementById("account-username-field").classList.remove("hidden");
  document.getElementById("account-role-field").classList.remove("hidden");
  form.elements.username.required = true;
  form.elements.password.required = true;
  fillAvatarOptions("child", "boy");
  showModal("account-form");
}

function openEditAccount(id) {
  const account = (appState.data.account_overview || []).find((item) => Number(item.id) === Number(id));
  if (!account) return;
  appState.accountEditId = Number(id);
  const form = document.getElementById("account-form");
  form.reset();
  document.getElementById("account-modal-title").textContent = `编辑 ${account.display_name}`;
  document.getElementById("account-username-field").classList.add("hidden");
  document.getElementById("account-role-field").classList.add("hidden");
  form.elements.username.required = false;
  form.elements.display_name.value = account.display_name;
  form.elements.password.required = false;
  fillAvatarOptions(account.role, account.avatar);
  showModal("account-form");
}

function showModal(formId) {
  ["editor-form", "manual-form", "account-form"].forEach((id) => document.getElementById(id).classList.toggle("hidden", id !== formId));
  document.getElementById("modal-backdrop").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("modal-backdrop")?.classList.add("hidden");
}

function findItem(kind, id) {
  const source = kind === "earn" ? appState.data.earn_items : kind === "exchange" || kind === "reward" ? appState.data.rewards : appState.data.deduct_items;
  return source.find((item) => Number(item.id) === Number(id));
}

async function saveAccount(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = { display_name: form.elements.display_name.value.trim(), password: form.elements.password.value, avatar: form.elements.avatar.value };
  try {
    if (appState.accountEditId) {
      await api(`/api/accounts/${appState.accountEditId}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("账号资料已更新");
    } else {
      payload.username = form.elements.username.value.trim();
      payload.role = form.elements.role.value;
      await api("/api/accounts", { method: "POST", body: JSON.stringify(payload) });
      showToast("账号已创建");
    }
    closeModal();
    await loadState();
    navigate("accounts");
  } catch (error) { showToast(error.message); }
}

async function deleteAccount(id) {
  if (!window.confirm("删除账号会同时删除积分和记录，确定继续吗？")) return;
  try { await api(`/api/accounts/${id}`, { method: "DELETE" }); await loadState(); navigate("accounts"); showToast("账号已删除"); } catch (error) { showToast(error.message); }
}

async function reviewRequest(action, id) {
  const message = action === "approve" ? "通过后积分会立即计入娃娃余额，确定吗？" : "确定拒绝这条申请吗？";
  if (!window.confirm(message)) return;
  try {
    appState.data = await api(`/api/requests/${id}/${action}`, { method: "POST", body: JSON.stringify(action === "reject" ? { reason: "管理账号拒绝了这条申请" } : {}) });
    if (appState.data.user.role === "admin") appState.accounts = (await api("/api/accounts")).accounts;
    render();
    showToast(action === "approve" ? "申请已通过" : "申请已拒绝");
  } catch (error) { showToast(error.message); }
}

async function handleOperation(kind, id = null, form = null) {
  const item = id ? findItem(kind, id) : null;
  const name = form ? form.elements.name.value.trim() : item?.name || "";
  const points = form ? Number(form.elements.points.value) : Math.abs(Number(item?.points));
  if (!Number.isInteger(points) || points <= 0) throw new Error("请输入有效积分");
  const payload = { kind, name, points };
  if (item) payload.item_id = item.id;
  if (kind === "exchange" && item) {
    delete payload.item_id;
    payload.reward_id = item.id;
  }
  const result = await api("/api/transactions", { method: "POST", body: JSON.stringify(payload) });
  appState.data = result;
  if (form) form.reset();
  render();
  showToast(result.request_submitted ? "申请已提交，等待管理账号审核" : kind === "earn" ? "已给娃娃加分" : kind === "exchange" ? "兑换已提交，等待管理账号审核" : "已扣取娃娃积分");
}

async function saveEditor(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = { name: form.elements.name.value.trim(), points: Number(form.elements.points.value), icon: appState.selectedIcon || form.elements.icon.value };
  if (!payload.name || !Number.isInteger(payload.points) || payload.points <= 0) { showToast("请填写有效项目和积分"); return; }
  try {
    const url = appState.editorId ? `/api/items/${appState.editorKind}/${appState.editorId}` : `/api/items/${appState.editorKind}`;
    await api(url, { method: appState.editorId ? "PUT" : "POST", body: JSON.stringify(payload) });
    closeModal();
    await loadState();
    showToast(appState.editorId ? "项目已更新" : "项目已添加");
  } catch (error) { showToast(error.message); }
}

async function saveManual(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const points = Number(form.elements.points.value);
  if (!Number.isInteger(points) || points === 0) { showToast("积分数值不能为 0"); return; }
  try {
    appState.data = await api("/api/transactions", { method: "POST", body: JSON.stringify({ kind: "manual", name: form.elements.name.value.trim(), points, date: form.elements.date.value }) });
    appState.selectedDate = form.elements.date.value;
    closeModal();
    render();
    showToast("积分已补录");
  } catch (error) { showToast(error.message); }
}

async function deleteItem(kind, id) {
  if (!window.confirm("确定删除这个项目吗？")) return;
  try { await api(`/api/items/${kind}/${id}`, { method: "DELETE" }); await loadState(); showToast("项目已删除"); } catch (error) { showToast(error.message); }
}

async function undoRecord(id) {
  if (!window.confirm("撤销后积分余额会回滚，确定继续吗？")) return;
  try { appState.data = await api(`/api/transactions/${id}/undo`, { method: "POST" }); render(); showToast("记录已撤销"); } catch (error) { showToast(error.message); }
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2600);
}

document.addEventListener("click", async (event) => {
  const pageTarget = event.target.closest("[data-page-target]");
  if (pageTarget) { navigate(pageTarget.dataset.pageTarget); return; }
  const dateTarget = event.target.closest("[data-select-date]");
  if (dateTarget) { appState.selectedDate = dateTarget.dataset.selectDate; navigate("records"); return; }
  const iconTarget = event.target.closest("[data-project-icon]");
  if (iconTarget) {
    appState.selectedIcon = iconTarget.dataset.projectIcon;
    renderIconPicker();
    return;
  }
  const editorTarget = event.target.closest("[data-open-editor]");
  if (editorTarget) { openEditor(editorTarget.dataset.openEditor); return; }
  const closeTarget = event.target.closest("[data-close-modal]");
  if (closeTarget) { closeModal(); return; }
  const action = event.target.closest("[data-action]");
  if (!action) return;
  try {
    if (["earn", "deduct", "exchange"].includes(action.dataset.action)) await handleOperation(action.dataset.action, Number(action.dataset.id));
    if (action.dataset.action === "edit") openEditor(action.dataset.kind, Number(action.dataset.id));
    if (action.dataset.action === "delete") await deleteItem(action.dataset.kind, Number(action.dataset.id));
    if (action.dataset.action === "edit-account") openEditAccount(Number(action.dataset.id));
    if (action.dataset.action === "delete-account") await deleteAccount(Number(action.dataset.id));
    if (action.dataset.action === "approve-request") await reviewRequest("approve", Number(action.dataset.id));
    if (action.dataset.action === "reject-request") await reviewRequest("reject", Number(action.dataset.id));
    if (action.dataset.action === "undo") await undoRecord(Number(action.dataset.id));
  } catch (error) { showToast(error.message); }
});

document.addEventListener("submit", async (event) => {
  if (event.target.matches("[data-kind]")) {
    event.preventDefault();
    try { await handleOperation(event.target.dataset.kind, null, event.target); } catch (error) { showToast(error.message); }
  }
});

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username: form.elements.username.value.trim(), password: form.elements.password.value }) });
    form.reset();
    appState.page = "home";
    await loadState();
  } catch (error) { document.getElementById("login-error").textContent = error.message; }
});

document.getElementById("editor-form").addEventListener("submit", saveEditor);
document.getElementById("manual-form").addEventListener("submit", saveManual);
document.getElementById("account-form").addEventListener("submit", saveAccount);
document.getElementById("open-account").addEventListener("click", openAccount);
document.getElementById("open-manual").addEventListener("click", openManual);
document.getElementById("account-form").elements.role.addEventListener("change", (event) => fillAvatarOptions(event.target.value));
document.getElementById("logout-button").addEventListener("click", async () => { try { await api("/api/auth/logout", { method: "POST" }); } finally { showLogin(); } });
document.getElementById("child-select").addEventListener("change", async (event) => {
  try { appState.data = await api("/api/auth/select-child", { method: "POST", body: JSON.stringify({ child_id: Number(event.target.value) }) }); navigate("home"); showToast(`已切换到 ${appState.data.active_child.display_name}`); } catch (error) { showToast(error.message); }
});
document.getElementById("prev-month").addEventListener("click", () => { if (appState.historyMonth === 0) { appState.historyMonth = 11; appState.historyYear -= 1; } else appState.historyMonth -= 1; renderHistory(); });
document.getElementById("next-month").addEventListener("click", () => { if (appState.historyMonth === 11) { appState.historyMonth = 0; appState.historyYear += 1; } else appState.historyMonth += 1; renderHistory(); });
document.getElementById("modal-backdrop").addEventListener("click", (event) => { if (event.target.id === "modal-backdrop") closeModal(); });
document.getElementById("clear-points").addEventListener("click", async () => {
  if (!window.confirm("确定清空当前娃娃的全部积分记录吗？")) return;
  try { appState.data = await api("/api/system/clear", { method: "POST" }); render(); showToast("积分记录已清空"); } catch (error) { showToast(error.message); }
});
document.getElementById("reset-system").addEventListener("click", async () => {
  if (!window.confirm("确定恢复当前娃娃的默认设置吗？")) return;
  try { appState.data = await api("/api/system/reset", { method: "POST" }); render(); showToast("当前娃娃已恢复默认设置"); } catch (error) { showToast(error.message); }
});

loadState();
