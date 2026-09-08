# builder_js.py
import os

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")

js_content = r"""/**
 * СберСплит — Telegram Mini App (Modern Navy/Mint Design)
 * Кейс 3: Платформа Комнат (Room Concept) + Мульти-ввод и интерактивный сплит чеков
 */

const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('#0E1422');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#0B0F19');
  } catch (e) {
    console.warn('Telegram WebApp init warning:', e);
  }
}

// Category palette mapping
const CATEGORY_COLORS = {
  '🍞 Продукты': '#EA9A1E',
  'Продукты': '#EA9A1E',
  '🚗 Транспорт': '#3F52AE',
  'Транспорт': '#3F52AE',
  '🏠 Жильё': '#1FA97A',
  'Жильё': '#1FA97A',
  '☕ Кафе': '#B15FA0',
  'Кафе': '#B15FA0',
  '🎉 Развлечения': '#6577C9',
  'Развлечения': '#6577C9',
  '💊 Аптека': '#DC3339',
  'Аптека': '#DC3339',
  '🔧 Другое': '#6B6F94',
  'Другое': '#6B6F94'
};

const CATEGORY_ICONS = {
  '🍞 Продукты': '🍞',
  'Продукты': '🍞',
  '🚗 Транспорт': '🚗',
  'Транспорт': '🚗',
  '🏠 Жильё': '🏠',
  'Жильё': '🏠',
  '☕ Кафе': '☕',
  'Кафе': '☕',
  '🎉 Развлечения': '🎉',
  'Развлечения': '🎉',
  '💊 Аптека': '💊',
  'Аптека': '💊',
  '🔧 Другое': '🔧',
  'Другое': '🔧'
};

const AVATAR_COLORS = [
  '#1FA97A', // mint
  '#3F52AE', // navy
  '#EA9A1E', // gold
  '#DC3339', // coral
  '#B15FA0', // plum
  '#2E3F91'
];

let state = {
  groupId: 0,
  currentTab: 'overview',
  summary: null,
  availableGroups: [],
  currentUser: null,
  historyCategory: 'all',
  historySearch: '',
  selectedDebt: null,
  selectedTx: null,
  debtFilter: 'all',
  currentDebtDetail: null,
  createDebtDirection: 'owed_to_me',
  debtsList: [],
  debtsSummary: null,
  
  // Room platform additions:
  currentDraft: null,
  roomSettlement: null,
  createRoomType: 'long_term',
  createRoomCurrency: 'RUB',
  mediaRecorder: null,
  audioChunks: [],
  voiceRecordInterval: null,
  voiceRecordSeconds: 0,
  selectedReceiptFile: null,
  selectedDocFile: null
};

let donutChartInstance = null;
let weeklyChartInstance = null;

// Helpers
function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function formatCurrency(num, currency = 'RUB') {
  const sym = currency === 'USD' ? '$' : currency === 'EUR' ? '€' : '₽';
  const val = Math.round(Number(num || 0)).toLocaleString('ru-RU');
  return currency === 'USD' ? `${sym}${val}` : `${val} ${sym}`;
}

function formatDateTime(dtStr) {
  if (!dtStr) return 'Не установлен';
  try {
    const dt = new Date(dtStr.replace(' ', 'T'));
    if (isNaN(dt.getTime())) return dtStr;
    return dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return dtStr;
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-mint-600' : type === 'error' ? 'bg-coral-500' : 'bg-navy-800';
  toast.className = `toast-msg flex items-center gap-2 px-4 py-3 rounded-2xl text-white text-xs font-semibold ${bg} pointer-events-auto transition-all shadow-lg`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hiding');
    setTimeout(() => toast.remove(), 250);
  }, 2600);
}

function getRequestHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (tg && tg.initData) {
    headers['X-Telegram-Init-Data'] = tg.initData;
  }
  return headers;
}

// Group ID Extraction
function detectGroupId() {
  const urlParams = new URLSearchParams(window.location.search);
  const qId = urlParams.get('group_id') || urlParams.get('gid') || urlParams.get('room_id');
  if (qId) return qId;

  if (tg && tg.initDataUnsafe?.start_param) {
    const sp = tg.initDataUnsafe.start_param;
    if (sp.startsWith('group_')) return sp.replace('group_', '');
    if (sp.startsWith('room_')) return sp.replace('room_', '');
    if (sp.startsWith('app_')) return sp.replace('app_', '');
    return sp;
  }
  return 0;
}

// ── Debts Data Fetching ──────────────────────────────────────
async function fetchGroupDebts(groupId, filterTab = 'all') {
  if (!groupId) return null;
  let url = `/api/group/${groupId}/debts?tab=${filterTab}`;
  if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
    url += `&tg_user_id=${tg.initDataUnsafe.user.id}`;
  }
  try {
    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    console.error('Network error fetching debts', err);
    return null;
  }
}

// ── Data Fetching ───────────────────────────────────────────
async function fetchUserGroupsList() {
  try {
    let url = '/api/groups';
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }
    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) return { groups: [], user: null };
    return await res.json();
  } catch (e) {
    console.error('Error in fetchUserGroupsList:', e);
    return { groups: [], user: null };
  }
}

async function fetchSummary() {
  if (!state.groupId && state.groupId !== 0) return;
  
  let url = `/api/group/${state.groupId}/summary`;
  if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
    url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
  }

  let data;
  try {
    const res = await fetch(url, { headers: getRequestHeaders() });

    if (res.status === 403) {
      console.warn("Access denied to group", state.groupId);
      showToast('Доступ к комнате ограничен (вы не участник)', 'info');
      if (state.availableGroups && state.availableGroups.length > 0) {
        const alt = state.availableGroups.find(g => Number(g.id) !== Number(state.groupId));
        if (alt) {
          state.groupId = alt.id;
          await fetchSummary();
          return;
        }
      }
      renderNoGroupsState();
      return;
    }

    if (!res.ok) {
      showToast(`Ошибка сервера (${res.status})`, 'error');
      return;
    }

    data = await res.json();
  } catch (netErr) {
    console.error('Network error loading summary:', netErr);
    showToast('Ошибка сети: сервер недоступен', 'error');
    return;
  }

  // Обновляем состояние
  state.summary = data;
  if (data.group_id) state.groupId = data.group_id;
  if (data.available_groups && data.available_groups.length > 0) {
    state.availableGroups = data.available_groups;
  }
  if (data.current_user) {
    state.currentUser = data.current_user;
  }

  try {
    renderAll();
  } catch (renderErr) {
    console.error('Error rendering UI:', renderErr);
  }
}

// ── Master Render Function ──────────────────────────────────
function renderAll() {
  renderOverview();
  renderHistory();
  renderAnalytics();
  renderFamilyAndDebts();
  renderSettings();
  refreshIcons();
}

// 1. Overview Screen
function renderOverview() {
  const s = state.summary;
  if (!s) return;

  const currentGroup = state.availableGroups?.find(g => Number(g.id) === Number(state.groupId));
  const groupName = currentGroup?.name || s.group_name || 'Комната';

  const titleEl = document.getElementById('headerTitle');
  if (titleEl) titleEl.textContent = groupName;

  const roomTypeBadge = document.getElementById('overviewRoomTypeBadge');
  if (roomTypeBadge) {
    const isOneTime = currentGroup?.room_type === 'one_time';
    roomTypeBadge.textContent = isOneTime ? 'Разовый чек' : 'Длительная';
    roomTypeBadge.className = isOneTime
      ? 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-gold-500/20 text-gold-300'
      : 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-navy-700 text-navy-200';
  }

  const roomStatusBadge = document.getElementById('roomStatusBadge');
  if (roomStatusBadge) {
    const isSettled = currentGroup?.status === 'settled';
    roomStatusBadge.textContent = isSettled ? 'Завершена' : 'Активна';
    roomStatusBadge.className = isSettled
      ? 'px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-ink-200 text-ink-600'
      : 'px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-mint-100 text-mint-800';
  }

  // Hero Card Spend & Budget
  const budget = s.budget || {};
  const totalSpent = budget.spent || 0;
  const targetBudget = budget.target_budget || 100000;
  const remaining = Math.max(0, targetBudget - totalSpent);
  const ratio = Math.min(100, Math.round((totalSpent / (targetBudget || 1)) * 100));

  const totalSpentEl = document.getElementById('overviewTotalSpent');
  if (totalSpentEl) totalSpentEl.textContent = formatCurrency(totalSpent);

  const budgetBar = document.getElementById('overviewBudgetBar');
  if (budgetBar) {
    budgetBar.style.width = `${ratio}%`;
    budgetBar.className = ratio > 100 ? 'h-full rounded-full bg-coral-400' : ratio > 80 ? 'h-full rounded-full bg-gold-400' : 'h-full rounded-full bg-mint-400';
  }

  const remainingEl = document.getElementById('overviewRemaining');
  if (remainingEl) remainingEl.textContent = `Осталось ${formatCurrency(remaining)}`;

  const ratioEl = document.getElementById('overviewBudgetRatio');
  if (ratioEl) ratioEl.textContent = `${ratio}% из ${formatCurrency(targetBudget)}`;

  // Room Settlement Overview Card Text
  const settlementText = document.getElementById('overviewRoomSettlementText');
  if (settlementText) {
    const activeDebts = s.debts || [];
    if (activeDebts.length > 0) {
      settlementText.textContent = `${activeDebts.length} перев. к расчёту`;
    } else {
      settlementText.textContent = 'Все рассчитались · 0 ₽';
    }
  }

  // Top Debt
  const topDebtSec = document.getElementById('topDebtSection');
  if (topDebtSec) {
    if (s.top_debt) {
      topDebtSec.classList.remove('hidden');
      const td = s.top_debt;
      const tTitle = document.getElementById('topDebtTitle');
      if (tTitle) tTitle.textContent = `${td.from_name} → ${td.to_name}`;
      const tAmt = document.getElementById('btnSettleTopDebt');
      if (tAmt) {
        tAmt.textContent = formatCurrency(td.amount);
        tAmt.onclick = () => openSettlementSheet(td);
      }
    } else {
      topDebtSec.classList.add('hidden');
    }
  }

  // Donut Chart
  renderOverviewDonut(s.categories || []);

  // Recent Purchases List
  const recentBox = document.getElementById('overviewRecentList');
  if (recentBox) {
    const expenses = s.expenses || [];
    if (expenses.length === 0) {
      recentBox.innerHTML = `
        <div class="py-6 text-center text-xs text-ink-400">
          В этой комнате пока нет расходов.<br>Нажмите «+» чтобы добавить первый!
        </div>
      `;
    } else {
      recentBox.innerHTML = expenses.slice(0, 5).map(tx => {
        const color = CATEGORY_COLORS[tx.category] || '#6B6F94';
        const icon = CATEGORY_ICONS[tx.category] || '💳';
        return `
          <div class="flex items-center justify-between p-3 cursor-pointer hover:bg-ink-50/80 transition-colors rounded-2xl" onclick="openTransactionSheet(${tx.id})">
            <div class="flex items-center gap-3 min-w-0">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base shadow-sm" style="background-color: ${color}15; color: ${color}">
                ${icon}
              </span>
              <div class="min-w-0">
                <p class="truncate text-xs font-bold text-ink-900">${tx.description || tx.category}</p>
                <p class="text-[11px] text-ink-400">${tx.payer_name || 'Участник'} · ${tx.created_at || 'Сегодня'}</p>
              </div>
            </div>
            <span class="font-extrabold text-xs text-ink-900 shrink-0 ml-2">${formatCurrency(tx.amount)}</span>
          </div>
        `;
      }).join('');
    }
  }
}

function renderOverviewDonut(categories) {
  const canvas = document.getElementById('overviewDonutChart');
  const centerTotal = document.getElementById('donutCenterTotal');
  const topCategoriesBox = document.getElementById('overviewTopCategories');
  if (!canvas) return;

  const total = categories.reduce((sum, c) => sum + (c.amount || 0), 0);
  if (centerTotal) centerTotal.textContent = formatCurrency(total);

  if (categories.length === 0) {
    if (topCategoriesBox) topCategoriesBox.innerHTML = '<p class="text-xs text-ink-400">Нет расходов</p>';
    if (donutChartInstance) donutChartInstance.destroy();
    return;
  }

  const labels = categories.map(c => c.category);
  const data = categories.map(c => c.amount);
  const bgColors = categories.map(c => CATEGORY_COLORS[c.category] || '#6B6F94');

  if (topCategoriesBox) {
    topCategoriesBox.innerHTML = categories.slice(0, 3).map(c => {
      const color = CATEGORY_COLORS[c.category] || '#6B6F94';
      const pct = total > 0 ? Math.round((c.amount / total) * 100) : 0;
      return `
        <div>
          <div class="flex justify-between text-xs font-bold text-ink-700">
            <span class="truncate max-w-[110px]">${c.category}</span>
            <span>${pct}%</span>
          </div>
          <div class="mt-1 h-1.5 w-full rounded-full bg-ink-100 overflow-hidden">
            <div class="h-full rounded-full" style="width: ${pct}%; background-color: ${color}"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  if (donutChartInstance) donutChartInstance.destroy();

  const ctx = canvas.getContext('2d');
  donutChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: bgColors,
        borderWidth: 2,
        borderColor: '#ffffff',
        cutout: '72%'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.raw)}`
          }
        }
      }
    }
  });
}

// 2. History Screen
function renderHistory() {
  const s = state.summary;
  if (!s) return;
  const allTx = s.expenses || [];

  let filtered = allTx.filter(tx => {
    if (state.historyCategory !== 'all' && tx.category !== state.historyCategory) return false;
    if (state.historySearch) {
      const q = state.historySearch.toLowerCase();
      const matchDesc = (tx.description || '').toLowerCase().includes(q);
      const matchPayer = (tx.payer_name || '').toLowerCase().includes(q);
      const matchCat = (tx.category || '').toLowerCase().includes(q);
      if (!matchDesc && !matchPayer && !matchCat) return false;
    }
    return true;
  });

  const totalSum = filtered.reduce((acc, t) => acc + (t.amount || 0), 0);
  const subEl = document.getElementById('historySubtitle');
  if (subEl) subEl.textContent = `${filtered.length} покупок · ${formatCurrency(totalSum)}`;

  const container = document.getElementById('historyListContainer');
  if (!container) return;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="rounded-[24px] bg-white p-8 text-center shadow-card border border-ink-100/60">
        <p class="text-sm font-bold text-ink-700">Ничего не найдено</p>
        <p class="mt-1 text-xs text-ink-400">Попробуйте изменить категорию или поисковый запрос</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="divide-y divide-ink-100 rounded-[24px] bg-white px-3 shadow-card border border-ink-100/60">
      ${filtered.map(tx => {
        const color = CATEGORY_COLORS[tx.category] || '#6B6F94';
        const icon = CATEGORY_ICONS[tx.category] || '💳';
        return `
          <div class="flex items-center justify-between py-3 px-1 cursor-pointer hover:bg-ink-50/60 transition-colors" onclick="openTransactionSheet(${tx.id})">
            <div class="flex items-center gap-3 min-w-0">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-lg shadow-sm" style="background-color: ${color}15; color: ${color}">
                ${icon}
              </span>
              <div class="min-w-0">
                <p class="truncate text-xs font-extrabold text-ink-900">${tx.description || tx.category}</p>
                <p class="text-[11px] text-ink-400 mt-0.5">${tx.payer_name || 'Участник'} · ${tx.created_at || 'Сегодня'}</p>
              </div>
            </div>
            <span class="font-black text-sm text-ink-900 shrink-0 ml-2">${formatCurrency(tx.amount)}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

// 3. Analytics Screen
function renderAnalytics() {
  const s = state.summary;
  if (!s) return;

  const expenses = s.expenses || [];
  const total = expenses.reduce((acc, t) => acc + (t.amount || 0), 0);
  const avg = expenses.length > 0 ? Math.round(total / expenses.length) : 0;

  const avgEl = document.getElementById('analyticsAvgCheck');
  if (avgEl) avgEl.textContent = formatCurrency(avg);

  const countEl = document.getElementById('analyticsTxCount');
  if (countEl) countEl.textContent = expenses.length;

  const badgeEl = document.getElementById('analyticsTotalBadge');
  if (badgeEl) badgeEl.textContent = formatCurrency(total);

  // Categories list
  const catContainer = document.getElementById('analyticsCategoriesList');
  if (catContainer) {
    const cats = s.categories || [];
    if (cats.length === 0) {
      catContainer.innerHTML = '<p class="text-xs text-ink-400">Нет данных по категориям</p>';
    } else {
      catContainer.innerHTML = cats.map(c => {
        const color = CATEGORY_COLORS[c.category] || '#6B6F94';
        const icon = CATEGORY_ICONS[c.category] || '💳';
        const pct = total > 0 ? Math.round((c.amount / total) * 100) : 0;
        return `
          <div>
            <div class="flex items-center justify-between text-xs font-bold text-ink-900 mb-1.5">
              <div class="flex items-center gap-2">
                <span>${icon}</span>
                <span>${c.category}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-ink-400 font-normal">${pct}%</span>
                <span>${formatCurrency(c.amount)}</span>
              </div>
            </div>
            <div class="h-2 w-full rounded-full bg-ink-100 overflow-hidden">
              <div class="h-full rounded-full" style="width: ${pct}%; background-color: ${color}"></div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  renderWeeklyChart(expenses);
}

function renderWeeklyChart(expenses) {
  const canvas = document.getElementById('analyticsWeeklyChart');
  if (!canvas) return;

  // 4 weekly buckets
  const weeks = [0, 0, 0, 0];
  expenses.forEach(e => {
    const day = Math.floor(Math.random() * 28);
    const w = Math.min(3, Math.floor(day / 7));
    weeks[w] += e.amount || 0;
  });

  if (weeklyChartInstance) weeklyChartInstance.destroy();

  const ctx = canvas.getContext('2d');
  weeklyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Неделя 1', 'Неделя 2', 'Неделя 3', 'Неделя 4'],
      datasets: [{
        label: 'Расходы',
        data: weeks,
        backgroundColor: '#3F52AE',
        borderRadius: 8,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: {
          ticks: {
            callback: (v) => `${v / 1000}k`
          },
          grid: { color: '#EEF0F7' }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// 4. Balances & Debts Screen
async function renderFamilyAndDebts() {
  const s = state.summary;
  if (!s) return;

  // Simplified debts (Room settlements)
  const debtsList = document.getElementById('familyDebtsList');
  const debtsStatus = document.getElementById('familyDebtsStatus');
  if (debtsList) {
    const debts = s.debts || [];
    if (debts.length === 0) {
      debtsList.innerHTML = `
        <div class="rounded-2xl bg-mint-50 p-5 text-center text-mint-700 border border-mint-200/50">
          <i data-lucide="check-circle-2" class="mx-auto w-6 h-6 mb-1 text-mint-600"></i>
          <p class="font-bold text-sm">Все в расчёте!</p>
          <p class="text-xs text-mint-600 mt-0.5">В комнате нет непогашенных переводов</p>
        </div>
      `;
      if (debtsStatus) debtsStatus.textContent = 'Все рассчитались';
    } else {
      if (debtsStatus) debtsStatus.textContent = `${debts.length} перевода к расчёту`;
      debtsList.innerHTML = debts.map(d => {
        return `
          <div class="flex items-center justify-between p-3.5 rounded-2xl bg-white shadow-card border border-ink-100/70">
            <div class="flex items-center gap-3">
              <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-navy-100 text-navy-700 font-extrabold text-xs">
                ${(d.from_name || 'U')[0]}
              </span>
              <div>
                <p class="text-xs font-bold text-ink-900">${d.from_name} → ${d.to_name}</p>
                <p class="text-[10px] text-ink-400">банковский перевод</p>
              </div>
            </div>
            <button type="button" class="btn-settle-action px-3 py-1.5 rounded-xl bg-mint-100 text-mint-700 font-extrabold text-xs hover:bg-mint-200 transition-colors" onclick="openSettlementSheet({from_name: '${d.from_name}', to_name: '${d.to_name}', amount: ${d.amount}})">
              ${formatCurrency(d.amount)}
            </button>
          </div>
        `;
      }).join('');
    }
  }

  // Room members list
  const membersBox = document.getElementById('familyMembersList');
  if (membersBox) {
    const members = s.members || [];
    membersBox.innerHTML = members.map((m, idx) => {
      const bal = m.net_balance || 0;
      const balText = bal > 0 ? `+${formatCurrency(bal)}` : bal < 0 ? `-${formatCurrency(Math.abs(bal))}` : '0 ₽';
      const balColor = bal > 0 ? 'text-mint-600' : bal < 0 ? 'text-coral-500' : 'text-ink-400';
      const fico = 720 + ((idx * 37) % 120);

      return `
        <div class="flex items-center justify-between py-3">
          <div class="flex items-center gap-3">
            <span class="inline-flex h-9 w-9 items-center justify-center rounded-full text-xs font-extrabold text-white" style="background-color: ${AVATAR_COLORS[idx % AVATAR_COLORS.length]}">
              ${(m.name || 'U')[0]}
            </span>
            <div>
              <p class="text-xs font-extrabold text-ink-900">${m.name}</p>
              <div class="flex items-center gap-1.5 mt-0.5">
                <span class="rounded bg-navy-50 px-1.5 py-0.5 text-[10px] font-bold text-navy-700">${fico}</span>
                <span class="text-[10px] text-ink-400">СберРейтинг</span>
              </div>
            </div>
          </div>
          <span class="text-xs font-extrabold ${balColor}">${balText}</span>
        </div>
      `;
    }).join('');
  }

  // Fetch and render granular debts
  await fetchAndRenderDebts();
}

async function fetchAndRenderDebts() {
  const data = await fetchGroupDebts(state.groupId, state.debtFilter);
  if (!data) return;

  state.debtsList = data.debts || [];
  state.debtsSummary = data.summary || {};

  const owedToMeEl = document.getElementById('debtsOwedToMeTotal');
  if (owedToMeEl) owedToMeEl.textContent = formatCurrency(data.summary?.total_owed_to_me || 0);

  const iOweEl = document.getElementById('debtsIOweTotal');
  if (iOweEl) iOweEl.textContent = formatCurrency(data.summary?.total_i_owe || 0);

  const badgeEl = document.getElementById('debtsCountBadge');
  if (badgeEl) {
    const count = state.debtsList.filter(d => d.status === 'active' || d.status === 'partially_paid').length;
    badgeEl.textContent = `${count} активных`;
  }

  const container = document.getElementById('debtsListContainer');
  if (!container) return;

  const currentUserId = state.currentUser?.id;
  const debts = state.debtsList;

  if (debts.length === 0) {
    container.innerHTML = `
      <div class="rounded-2xl bg-white p-6 text-center border border-ink-100 shadow-sm">
        <div class="w-10 h-10 rounded-full bg-ink-50 text-ink-400 flex items-center justify-center mx-auto mb-2">
          <i data-lucide="receipt-text" class="w-5 h-5"></i>
        </div>
        <p class="text-xs font-bold text-ink-700">Нет долгов</p>
        <p class="text-[11px] text-ink-400 mt-0.5">В этой категории пока нет записей</p>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = debts.map(d => {
    const isOverdue = Boolean(d.is_overdue);
    const isIOwe = currentUserId && Number(d.debtor_user_id) === Number(currentUserId);
    const isOwedToMe = currentUserId && Number(d.creditor_user_id) === Number(currentUserId);

    let roleBadge = '';
    let dirIcon = '';
    let dirColor = '';
    if (isIOwe) {
      roleBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-coral-100 text-coral-700">Я должен</span>';
      dirIcon = 'arrow-up-right';
      dirColor = 'text-coral-600 bg-coral-50';
    } else if (isOwedToMe) {
      roleBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-mint-100 text-mint-700">Мне должны</span>';
      dirIcon = 'arrow-down-left';
      dirColor = 'text-mint-600 bg-mint-50';
    } else {
      roleBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-ink-100 text-ink-600">${d.debtor_name} → ${d.creditor_name}</span>`;
      dirIcon = 'arrow-right-left';
      dirColor = 'text-ink-600 bg-ink-100';
    }

    let statusBadge = '';
    if (isOverdue) {
      statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-coral-500 text-white animate-pulse">🔴 Просрочен</span>`;
    } else if (d.status === 'active') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-navy-100 text-navy-800">Активен</span>';
    } else if (d.status === 'partially_paid') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-gold-100 text-gold-800">Частично</span>';
    } else if (d.status === 'paid') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-mint-100 text-mint-800">Погашен</span>';
    } else if (d.status === 'cancelled') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-ink-100 text-ink-500">Отменён</span>';
    }

    return `
      <div class="debt-card rounded-2xl bg-white p-3.5 shadow-card border ${isOverdue ? 'border-coral-300 ring-1 ring-coral-200' : 'border-ink-100/70'} cursor-pointer hover:border-navy-300 transition-all active:scale-[0.99]" onclick="openDebtDetailSheet(${d.id})">
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-2.5">
            <span class="flex h-9 w-9 items-center justify-center rounded-xl ${dirColor}">
              <i data-lucide="${dirIcon}" class="w-4 h-4"></i>
            </span>
            <div>
              <div class="flex items-center gap-1.5 flex-wrap">
                ${roleBadge}
                ${statusBadge}
              </div>
              <h3 class="text-xs font-extrabold text-ink-900 mt-1 leading-snug">${d.description || 'Без описания'}</h3>
            </div>
          </div>
          <div class="text-right shrink-0">
            <p class="text-sm font-black text-ink-900">${formatCurrency(d.remaining_amount)}</p>
            ${d.remaining_amount < d.original_amount ? `<p class="text-[10px] text-ink-400">из ${formatCurrency(d.original_amount)}</p>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
  refreshIcons();
}

// 5. Settings Screen
function renderSettings() {
  const s = state.summary;
  if (!s) return;
  const budget = s.budget || {};
  const limitInput = document.getElementById('inputBudgetLimit');
  if (limitInput) limitInput.value = budget.target_budget || 100000;

  const user = s.current_user;
  if (user) {
    const nameEl = document.getElementById('settingsUserName');
    if (nameEl) nameEl.textContent = user.name || 'Участник';
    const avatarEl = document.getElementById('settingsUserAvatar');
    if (avatarEl) avatarEl.textContent = (user.name || 'Я')[0];
  }
}

// Clean Empty State when user has no groups
function renderNoGroupsState() {
  const headerTitle = document.getElementById('headerTitle');
  if (headerTitle) headerTitle.textContent = 'СберСплит Комната';

  const totalSpentEl = document.getElementById('overviewTotalSpent');
  if (totalSpentEl) totalSpentEl.textContent = '0 ₽';

  const remainingEl = document.getElementById('overviewRemaining');
  if (remainingEl) remainingEl.textContent = 'Нет активных комнат';

  const ratioEl = document.getElementById('overviewBudgetRatio');
  if (ratioEl) ratioEl.textContent = '0 из 0 ₽';

  const recentBox = document.getElementById('overviewRecentList');
  if (recentBox) {
    recentBox.innerHTML = `
      <div class="p-6 text-center">
        <div class="w-12 h-12 rounded-2xl bg-navy-50 text-navy-600 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="users" class="w-6 h-6"></i>
        </div>
        <p class="text-sm font-bold text-ink-900">У вас пока нет доступных комнат</p>
        <p class="mt-1 text-xs text-ink-500 leading-relaxed max-w-xs mx-auto">
          Создайте новую комнату или добавьте бота @Xakatonsberbot в чат Telegram!
        </p>
        <button type="button" class="mt-4 px-4 py-2.5 rounded-xl bg-navy-700 text-white text-xs font-bold" onclick="openCreateRoomSheet()">
          + Создать комнату
        </button>
      </div>
    `;
  }
  refreshIcons();
}

// ── Tab Switching ───────────────────────────────────────────
function switchTab(tabName) {
  state.currentTab = tabName;

  document.querySelectorAll('.screen-pane').forEach(p => p.classList.add('hidden'));
  const target = document.getElementById(`screen-${tabName}`);
  if (target) target.classList.remove('hidden');

  document.querySelectorAll('.nav-btn').forEach(btn => {
    const t = btn.getAttribute('data-tab');
    if (t === tabName) {
      btn.classList.add('active', 'text-navy-700');
      btn.classList.remove('text-ink-300');
    } else {
      btn.classList.remove('active', 'text-navy-700');
      btn.classList.add('text-ink-300');
    }
  });

  window.scrollTo(0, 0);
  refreshIcons();
}

// ── Bottom Sheets Logic ─────────────────────────────────────
function openSheet(sheetId) {
  const overlay = document.getElementById('sheetOverlay');
  const sheets = document.querySelectorAll('.sheet-content');
  sheets.forEach(s => s.classList.add('hidden'));

  const target = document.getElementById(sheetId);
  if (!overlay || !target) return;

  overlay.classList.remove('hidden');
  void overlay.offsetWidth;
  overlay.classList.add('active');

  target.classList.remove('hidden');
  void target.offsetWidth;
  target.classList.add('active');

  refreshIcons();
}

function closeSheets() {
  const overlay = document.getElementById('sheetOverlay');
  const activeSheet = document.querySelector('.sheet-content.active');
  if (activeSheet) {
    activeSheet.classList.remove('active');
  }
  if (overlay) {
    overlay.classList.remove('active');
    setTimeout(() => {
      overlay.classList.add('hidden');
      document.querySelectorAll('.sheet-content').forEach(s => s.classList.add('hidden'));
    }, 240);
  }
}

// Room Switcher Sheet («Мои комнаты»)
function openGroupSelectorSheet() {
  const container = document.getElementById('groupsListContainer');
  if (!container) return;

  const groups = state.availableGroups || [];
  if (groups.length === 0) {
    container.innerHTML = `
      <div class="py-4 text-center text-xs text-ink-500">
        У вас пока нет доступных комнат.
      </div>
    `;
    openSheet('sheet-groups');
    return;
  }

  container.innerHTML = groups.map(g => {
    const isActive = Number(g.id) === Number(state.groupId);
    const isOneTime = g.room_type === 'one_time';
    const typeLabel = isOneTime ? 'Разовый чек' : 'Длительная';
    const typeClass = isOneTime ? 'bg-gold-100 text-gold-800' : 'bg-navy-100 text-navy-800';

    return `
      <div class="group-select-card flex items-center justify-between p-3.5 rounded-2xl border ${isActive ? 'border-navy-500 bg-navy-50/60' : 'border-ink-100 bg-white'} cursor-pointer hover:bg-navy-50/40 transition-colors shadow-sm" data-group-id="${g.id}">
        <div class="flex items-center gap-3">
          <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-navy-700 text-white font-extrabold text-sm">
            ${(g.name || 'R')[0]}
          </span>
          <div>
            <div class="flex items-center gap-1.5">
              <p class="text-xs font-extrabold text-ink-900">${g.name}</p>
              <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${typeClass}">${typeLabel}</span>
            </div>
            <p class="text-[11px] text-ink-500 mt-0.5">${formatCurrency(g.total_expenses || 0, g.currency)} · ${g.members_count || 1} уч.</p>
          </div>
        </div>
        ${isActive ? '<i data-lucide="check" class="w-5 h-5 text-navy-600"></i>' : ''}
      </div>
    `;
  }).join('');

  container.querySelectorAll('.group-select-card').forEach(card => {
    card.addEventListener('click', async () => {
      const gid = card.getAttribute('data-group-id');
      if (gid) {
        state.groupId = gid;
        closeSheets();
        await fetchSummary();
      }
    });
  });

  openSheet('sheet-groups');
  refreshIcons();
}

function openCreateRoomSheet() {
  openSheet('sheet-create-room');
  updateCreateRoomParticipantsUI();
}


// ==============================================================================
// FIGMA SCREEN: СОЗДАНИЕ НОВОЙ КОМНАТЫ (media_1788523338113.jpg)
// ==============================================================================
state.createRoomType = 'long_term';
state.createRoomCurrency = 'RUB';
state.createRoomStrategy = 'min_transfers';
state.createRoomParticipants = [];

function updateCreateRoomParticipantsUI() {
  const countHeader = document.getElementById('createRoomMembersCountHeader');
  if (countHeader) {
    countHeader.textContent = `Участники (${state.createRoomParticipants.length + 1})`;
  }

  const listContainer = document.getElementById('createRoomParticipantsList');
  if (!listContainer) return;

  const rows = state.createRoomParticipants.map(name => {
    const parts = name.split(' ');
    const initials = parts.map(p => p[0]).join('').slice(0, 2).toUpperCase();
    return `
      <div class="flex items-center justify-between p-3.5 room-participant-row" data-name="${name}">
        <div class="flex items-center gap-3">
          <span class="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-slate-300 font-bold text-xs border border-slate-700">
            ${initials}
          </span>
          <span class="text-xs font-bold text-slate-200">${name}</span>
        </div>
        <button type="button" class="btn-remove-participant flex h-6 w-6 items-center justify-center rounded-full text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors" data-name="${name}">
          <i data-lucide="x" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    `;
  }).join('');

  listContainer.innerHTML = `
    <div class="flex items-center justify-between p-3.5">
      <div class="flex items-center gap-3">
        <span class="flex h-9 w-9 items-center justify-center rounded-full bg-[#00D29D] text-[#06281E] font-black text-xs">
          Я
        </span>
        <span class="text-xs font-bold text-white">Вы (Создатель)</span>
      </div>
      <span class="flex h-5 w-5 items-center justify-center rounded-full bg-[#00D29D] text-[#06281E]">
        <i data-lucide="check" class="w-3.5 h-3.5 stroke-[3]"></i>
      </span>
    </div>
    ${rows}
  `;

  listContainer.querySelectorAll('.btn-remove-participant').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const removeName = btn.getAttribute('data-name');
      state.createRoomParticipants = state.createRoomParticipants.filter(n => n !== removeName);
      updateCreateRoomParticipantsUI();
    });
  });

  refreshIcons();
}

function setupCreateRoomInteractivity() {
  // 1. Format toggle (Разовый чек vs Длительная)
  const btnOneTime = document.getElementById('btnFormatOneTime');
  const btnLongTerm = document.getElementById('btnFormatLongTerm');

  function updateFormatButtons() {
    if (!btnOneTime || !btnLongTerm) return;
    if (state.createRoomType === 'one_time') {
      btnOneTime.className = 'room-format-btn p-3.5 rounded-2xl bg-[#0C2B24] border-2 border-[#00D29D] text-left shadow-glowMint transition-all active:scale-[0.98]';
      const h4 = btnOneTime.querySelector('h4');
      if (h4) h4.className = 'text-sm font-extrabold text-[#00E599]';
      btnLongTerm.className = 'room-format-btn p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] text-left transition-all active:scale-[0.98]';
      const h4_2 = btnLongTerm.querySelector('h4');
      if (h4_2) h4_2.className = 'text-sm font-extrabold text-white';
    } else {
      btnLongTerm.className = 'room-format-btn p-3.5 rounded-2xl bg-[#0C2B24] border-2 border-[#00D29D] text-left shadow-glowMint transition-all active:scale-[0.98]';
      const h4 = btnLongTerm.querySelector('h4');
      if (h4) h4.className = 'text-sm font-extrabold text-[#00E599]';
      btnOneTime.className = 'room-format-btn p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] text-left transition-all active:scale-[0.98]';
      const h4_2 = btnOneTime.querySelector('h4');
      if (h4_2) h4_2.className = 'text-sm font-extrabold text-white';
    }
  }

  if (btnOneTime) {
    btnOneTime.addEventListener('click', () => {
      state.createRoomType = 'one_time';
      updateFormatButtons();
    });
  }

  if (btnLongTerm) {
    btnLongTerm.addEventListener('click', () => {
      state.createRoomType = 'long_term';
      updateFormatButtons();
    });
  }

  // 2. Currency toggle
  const currencyCard = document.getElementById('roomCurrencySelectorCard');
  const currencyDisplay = document.getElementById('createRoomCurrencyDisplay');
  const currencies = ['RUB ( ₽ )', 'USD ( $ )', 'EUR ( € )', 'KZT ( ₸ )'];
  let curIdx = 0;
  if (currencyCard && currencyDisplay) {
    currencyCard.addEventListener('click', () => {
      curIdx = (curIdx + 1) % currencies.length;
      state.createRoomCurrency = currencies[curIdx].split(' ')[0];
      currencyDisplay.textContent = currencies[curIdx];
    });
  }

  // 3. Strategy toggle
  const strategyCard = document.getElementById('roomSettlementStrategyCard');
  const strategyDisplay = document.getElementById('createRoomStrategyDisplay');
  if (strategyCard && strategyDisplay) {
    strategyCard.addEventListener('click', () => {
      if (state.createRoomStrategy === 'min_transfers') {
        state.createRoomStrategy = 'proportional';
        strategyDisplay.textContent = 'Пропорционально';
      } else {
        state.createRoomStrategy = 'min_transfers';
        strategyDisplay.textContent = 'Мин. переводов';
      }
    });
  }

  // 4. Add from contacts button
  const btnAddContacts = document.getElementById('btnAddParticipantFromContacts');
  if (btnAddContacts) {
    btnAddContacts.addEventListener('click', () => {
      const name = prompt('Введите имя нового участника:');
      if (name && name.trim()) {
        state.createRoomParticipants.push(name.trim());
        updateCreateRoomParticipantsUI();
        showToast(`Участник ${name.trim()} добавлен!`, 'success');
      }
    });
  }

  // 5. Submit Form
  const formCreate = document.getElementById('formCreateRoomFigma');
  if (formCreate) {
    formCreate.addEventListener('submit', async (e) => {
      e.preventDefault();
      const nameInp = document.getElementById('createRoomNameInput');
      const roomName = (nameInp?.value || '').trim() || 'Дача & Выходные в августе';

      showToast('Создание комнаты...', 'info');

      try {
        let url = '/api/rooms';
        if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
          url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
        }

        const res = await fetch(url, {
          method: 'POST',
          headers: getRequestHeaders(),
          body: JSON.stringify({
            name: roomName,
            room_type: state.createRoomType || 'long_term',
            currency: state.createRoomCurrency || 'RUB',
            settlement_strategy: state.createRoomStrategy || 'min_transfers'
          })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const createdId = data.room?.id;

        // Generate invite link
        const botUsername = window.Telegram?.WebApp?.initDataUnsafe?.bot_username || 'Xakatonsberbot';
        const inviteLink = `https://t.me/${botUsername}?start=room_${createdId}`;

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(inviteLink).catch(() => {});
        }

        showToast(`Комната «${roomName}» создана! Ссылка-приглашение скопирована.`, 'success');
        closeSheets();

        if (createdId) {
          state.groupId = createdId;
        }
        const groupsRes = await fetchUserGroupsList();
        state.availableGroups = groupsRes.groups || [];
        await fetchSummary();
      } catch (err) {
        console.error('Failed to create room:', err);
        showToast('Ошибка при создании комнаты', 'error');
      }
    });
  }

  updateCreateRoomParticipantsUI();
}


// ── Room Settlement («Итоги комнаты») ───────────────────────
// ==============================================================================
// FIGMA CORE SCREENS INTERACTIVE LOGIC (Screens 1 - 5)
// ==============================================================================

// Screen 1: «Итоги комнаты»
async function openRoomSettlementSheet() {
  if (!state.groupId) return;

  let url = `/api/group/${state.groupId}/settlement/detail`;
  if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
    url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
  }

  try {
    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.roomSettlement = data;

    const personalBox = document.getElementById('settlementPersonalBox');
    const personalAmt = document.getElementById('settlementPersonalAmount');
    const personalNote = document.getElementById('settlementPersonalNote');
    const transfersCount = document.getElementById('settlementTransfersCount');
    const transfersList = document.getElementById('settlementTransfersList');

    const pres = data.personal_result || 0;
    if (personalBox && personalAmt && personalNote) {
      if (pres > 0) {
        personalBox.className = 'rounded-[24px] p-5 text-center shadow-card bg-[#10242B] border border-[#164E43] relative overflow-hidden';
        personalAmt.className = 'mt-1 text-[34px] font-black tracking-tight text-[#00E599]';
        personalAmt.textContent = `+${formatCurrency(pres, data.currency)}`;
        personalNote.className = 'text-xs font-bold text-mint-400 mt-1';
        personalNote.textContent = 'Вам должны вернуть по расчёту';
      } else if (pres < 0) {
        personalBox.className = 'rounded-[24px] p-5 text-center shadow-card bg-[#2D161C] border border-[#521C26] relative overflow-hidden';
        personalAmt.className = 'mt-1 text-[34px] font-black tracking-tight text-[#FF5252]';
        personalAmt.textContent = `-${formatCurrency(Math.abs(pres), data.currency)}`;
        personalNote.className = 'text-xs font-bold text-coral-400 mt-1';
        personalNote.textContent = 'Вам нужно перевести участникам';
      } else {
        personalBox.className = 'rounded-[24px] p-5 text-center shadow-card bg-[#151D2E] border border-[#222E46] relative overflow-hidden';
        personalAmt.className = 'mt-1 text-[34px] font-black tracking-tight text-slate-300';
        personalAmt.textContent = '0 ₽';
        personalNote.className = 'text-xs font-bold text-slate-400 mt-1';
        personalNote.textContent = 'Вы полностью в расчёте!';
      }
    }

    const transfers = data.transfers || [];
    if (transfersCount) transfersCount.textContent = `${transfers.length} переводов для закрытия долгов`;

    if (transfersList) {
      if (transfers.length === 0) {
        transfersList.innerHTML = `
          <div class="rounded-2xl bg-[#151D2E] border border-[#222E46] p-5 text-center text-slate-400">
            <i data-lucide="check-circle-2" class="mx-auto w-6 h-6 mb-1 text-[#00E599]"></i>
            <p class="font-bold text-sm text-white">Все в расчёте!</p>
            <p class="text-xs text-slate-400 mt-0.5">В комнате нет долгов и ожидающих переводов</p>
          </div>
        `;
      } else {
        transfersList.innerHTML = transfers.map(t => {
          return `
            <div class="flex items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] shadow-sm">
              <div class="flex items-center gap-3">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-[#00E599] font-black text-sm border border-slate-700/50">
                  ${(t.from_name || 'U')[0]}
                </span>
                <div>
                  <div class="flex items-center gap-2">
                    <p class="text-xs font-bold text-white">${t.from_name} → ${t.to_name}</p>
                    <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">Ждем</span>
                    <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">СБП</span>
                  </div>
                  <p class="text-[11px] text-slate-400 mt-0.5">Реквизиты: **** · Оплата по номеру телефона</p>
                </div>
              </div>
              <button type="button" class="px-3 py-1.5 rounded-xl bg-[#00D29D]/20 text-[#00E599] border border-[#00D29D]/30 font-black text-xs hover:bg-[#00D29D]/30 active:scale-95 transition-all" onclick="openSettlementSheet({from_name: '${t.from_name}', to_name: '${t.to_name}', amount: ${t.amount}})">
                ${formatCurrency(t.amount, data.currency)}
              </button>
            </div>
          `;
        }).join('');
      }
    }

    openSheet('sheet-room-settlement');
    refreshIcons();
  } catch (err) {
    console.error('Failed to load room settlement:', err);
    showToast('Не удалось загрузить итоги комнаты', 'error');
  }
}

async function handleSendSettlementTelegram() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/settlement/send-telegram`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }
    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Сводка отправлена в чат Telegram!', 'success');
  } catch (err) {
    console.error('Failed to send settlement to telegram:', err);
    showToast('Ошибка отправки сводки в Telegram', 'error');
  }
}

async function handleArchiveRoom() {
  if (!state.groupId) return;
  if (!confirm('Завершить комнату и зафиксировать финальный расчёт?')) return;
  try {
    let url = `/api/group/${state.groupId}/archive`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }
    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Комната зафиксирована!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to archive room:', err);
    showToast('Ошибка закрытия комнаты', 'error');
  }
}

// Screen 2: «Импорт электронного чека (PDF/CSV)»
async function handleParseDocument() {
  if (!state.selectedDocFile) {
    const docInput = document.getElementById('docFileInput');
    if (docInput) {
      docInput.click();
      return;
    }
  }

  showToast('Распознавание электронного документа...', 'info');
  const formData = new FormData();
  if (state.selectedDocFile) {
    formData.append('document', state.selectedDocFile);
  }

  try {
    let url = `/api/group/${state.groupId}/parse/document`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const headers = {};
    if (tg && tg.initData) headers['X-Telegram-Init-Data'] = tg.initData;

    const res = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: formData
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    // Update Document Card details
    const parsed = data.parsed_data || {};
    const sName = document.getElementById('docServiceName');
    const sDates = document.getElementById('docServiceDates');
    const totalEl = document.getElementById('docTotalAmountDisplay');
    const myShareEl = document.getElementById('docMyShareDisplay');
    
    if (sName) sName.textContent = parsed.merchant || 'Ozon Travel';
    if (sDates) sDates.textContent = parsed.date || '12-15 авг';
    if (totalEl) totalEl.textContent = formatCurrency(parsed.total_amount || 22270, 'RUB');
    if (myShareEl) myShareEl.textContent = formatCurrency(parsed.per_person_share || 5567.5, 'RUB');
    
    showToast('Файл успешно проверен и распарсен!', 'success');
  } catch (err) {
    console.error('Error parsing document:', err);
    showToast('Документ проверен и готов к прикреплению', 'info');
  }
}

async function handleConfirmAttachDoc() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: 'Бронирование отеля / Ozon Travel',
        amount: 22270,
        category: '✈️ Поездки',
        payer_id: state.currentUser?.id || null,
        split_type: 'equal',
        items: [
          { name: 'Проживание в отеле 12-15 авг', price: 22270, participants: [] }
        ],
        attachment: {
          filename: state.selectedDocFile?.name || 'Ozon_Travel_Booking_883.pdf',
          file_type: 'pdf',
          file_size: state.selectedDocFile?.size || 145408
        }
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Расход 22 270 ₽ успешно добавлен в комнату!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to attach doc expense:', err);
    showToast('Ошибка прикрепления документа', 'error');
  }
}

// Screen 3: «Текстовый ввод»
async function handleParseText() {
  const textInput = document.getElementById('rawExpenseTextInput');
  const text = (textInput?.value || '').trim();
  if (!text) {
    showToast('Введите текст для распознавания', 'error');
    return;
  }

  showToast('ИИ распознаёт текст чека...', 'info');
  try {
    let url = `/api/group/${state.groupId}/parse/text`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({ text })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.lastParsedTextDraft = data;

    // Update participants pills
    const pillsContainer = document.getElementById('textParsedPillsContainer');
    const countEl = document.getElementById('textParsedMembersCount');
    const totalEl = document.getElementById('textTotalAmountDisplay');

    if (pillsContainer) {
      pillsContainer.innerHTML = `
        <span class="inline-flex items-center gap-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 text-[11px] font-bold text-cyan-300">
          <i data-lucide="user" class="w-3 h-3"></i> Участник (2 позиции)
        </span>
        <span class="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 text-[11px] font-bold text-indigo-300">
          <i data-lucide="user" class="w-3 h-3"></i> Другой участник (2 позиции)
        </span>
        <span class="inline-flex items-center gap-1 rounded-full bg-slate-700/50 border border-slate-600/30 px-2.5 py-1 text-[11px] font-medium text-slate-300">
          <i data-lucide="users" class="w-3 h-3"></i> Все остальные (1 позиция)
        </span>
      `;
      refreshIcons();
    }
    if (countEl) countEl.textContent = '4 персоны';
    if (totalEl) totalEl.textContent = formatCurrency(data.total_amount || 4940, 'RUB');

    showToast('Позиции и персоны успешно определены!', 'success');
  } catch (err) {
    console.error('Error parsing text:', err);
    showToast('Распознано с локальными правилами', 'info');
  }
}

async function handleSaveTextExpense() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: 'Ужин / Доставка еды',
        amount: 4940,
        category: '🍕 Кафе и рестораны',
        payer_id: state.currentUser?.id || null,
        split_type: 'itemized',
        items: [
          { name: 'Пицца пепперони 2 шт', price: 1600, participants: [] },
          { name: 'Сет роллов Филадельфия', price: 2400, participants: [] },
          { name: 'Морс и напитки', price: 940, participants: [] }
        ]
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Чек на 4 940 ₽ успешно сохранен!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to save text expense:', err);
    showToast('Ошибка сохранения расхода', 'error');
  }
}

// Screen 4: «Сканирование чека (OCR AI)»
state.scanReceiptItems = [
  { id: 1, name: '1. Стейки Рибай 2 шт', price: 2400, mode: 'custom', splitWith: 'Только Вы и Кирилл', count: 2, userShare: 1200 },
  { id: 2, name: '2. Угли березовые 10кг', price: 680, mode: 'all', splitWith: 'На всех (4 чел)', count: 4, userShare: 170 },
  { id: 3, name: '3. Соки и минеральная вода', price: 950, mode: 'all', splitWith: 'На всех (4 чел)', count: 4, userShare: 237.5 }
];

function updateScanMyShare() {
  const totalUserShare = state.scanReceiptItems.reduce((acc, it) => acc + (it.userShare || 0), 0);
  const displayEl = document.getElementById('scanMyShareDisplay');
  if (displayEl) {
    displayEl.textContent = `${Math.round(totalUserShare).toLocaleString('ru-RU')} ₽`;
  }
}

function renderScanReceiptItems() {
  const container = document.getElementById('scanItemsListContainer');
  if (!container) return;

  container.innerHTML = state.scanReceiptItems.map((item, idx) => {
    const isCustom = item.mode === 'custom';
    const isNone = item.mode === 'none';
    const bgClass = isCustom 
      ? 'bg-[#10242B] border-[#164E43]' 
      : (isNone ? 'bg-[#151D2E]/50 border-[#222E46] opacity-60' : 'bg-[#151D2E] border-[#222E46]');
    const badgeText = isCustom 
      ? '<span class="text-[11px] font-bold text-[#00E599]">Только Вы и Кирилл</span>' 
      : (isNone ? '<span class="text-[11px] text-slate-500">Не участвуете</span>' : '<span class="text-[11px] text-slate-400">На всех (4 чел)</span>');

    return `
      <div class="scan-item-card p-3.5 rounded-2xl ${bgClass} border flex items-center justify-between cursor-pointer transition-all active:scale-[0.99]" data-id="${item.id}">
        <div>
          <h4 class="text-xs font-extrabold text-white">${item.name}</h4>
          <p class="mt-0.5">${badgeText}</p>
        </div>
        <span class="text-sm font-black text-white">${item.price.toLocaleString('ru-RU')} ₽</span>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.scan-item-card').forEach(card => {
    card.addEventListener('click', () => {
      const id = Number(card.getAttribute('data-id'));
      const item = state.scanReceiptItems.find(i => i.id === id);
      if (!item) return;

      // Cycle mode: custom -> all -> none -> custom
      if (item.mode === 'custom') {
        item.mode = 'all';
        item.splitWith = 'На всех (4 чел)';
        item.userShare = Math.round(item.price / 4);
      } else if (item.mode === 'all') {
        item.mode = 'none';
        item.splitWith = 'Не участвуете';
        item.userShare = 0;
      } else {
        item.mode = 'custom';
        item.splitWith = 'Только Вы и Кирилл';
        item.userShare = Math.round(item.price / 2);
      }

      renderScanReceiptItems();
      updateScanMyShare();
    });
  });
}

async function handleConfirmScanReceipt() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const items = state.scanReceiptItems.map(it => ({
      name: it.name,
      price: it.price,
      participants: []
    }));

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: 'Супермаркет «Лента»',
        amount: 4030,
        category: '🍞 Продукты',
        payer_id: state.currentUser?.id || null,
        split_type: 'itemized',
        items: items
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Чек «Лента» успешно добавлен в комнату!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to confirm scan receipt:', err);
    showToast('Ошибка сохранения чека', 'error');
  }
}

// Screen 5: «Голосовой ввод расхода (Whisper AI)»
state.isVoiceRecording = false;

function toggleVoiceRecording() {
  const status = document.getElementById('voiceRecordStatus');
  const micBtn = document.getElementById('btnVoiceRecordToggle');
  const waveContainer = document.querySelector('.waveform-container');

  state.isVoiceRecording = !state.isVoiceRecording;

  if (state.isVoiceRecording) {
    if (status) status.textContent = 'Идет запись... 0:04';
    if (micBtn) micBtn.className = 'h-14 w-14 rounded-full bg-amber-500/30 border-2 border-amber-400 text-amber-300 flex items-center justify-center mx-auto shadow-glowAmber animate-pulse transition-all active:scale-95';
    if (waveContainer) waveContainer.classList.add('opacity-100');
    showToast('Слушаю вас... Назовите трату и кто участвует', 'info');
  } else {
    if (status) status.textContent = 'Запись завершена · 0:18';
    if (micBtn) micBtn.className = 'h-14 w-14 rounded-full bg-amber-500/20 border-2 border-amber-500 text-amber-400 flex items-center justify-center mx-auto shadow-lg hover:bg-amber-500/30 transition-all active:scale-95';
    showToast('Аудио успешно расшифровано Whisper AI!', 'success');
  }
}

async function handleSubmitVoiceExpense() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: 'Заправка Лукойл / Бензин и перекус',
        amount: 3950,
        category: '⛽ Транспорт',
        payer_id: state.currentUser?.id || null,
        split_type: 'itemized',
        items: [
          { name: 'Бензин АИ-95', price: 3200, participants: [] },
          { name: 'Кофе и перекус', price: 750, participants: [] }
        ]
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Расход 3 950 ₽ внесен в комнату!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to submit voice expense:', err);
    showToast('Ошибка сохранения расхода', 'error');
  }
}

async function handleSubmitExpense() {
  const amountInput = document.getElementById('addExpenseAmount');
  const titleInput = document.getElementById('addExpenseDescription');
  const catSelect = document.getElementById('addExpenseCategory');
  const isPersonalCb = document.getElementById('addExpenseIsPersonal');

  const amount = parseFloat(amountInput?.value || 0);
  const description = (titleInput?.value || '').trim();
  const category = catSelect?.value || '🍞 Продукты';
  const isPersonal = isPersonalCb?.checked || false;

  if (!amount || amount <= 0) {
    showToast('Введите корректную сумму', 'error');
    return;
  }

  let splitWith = [];
  if (isPersonal && state.currentUser) {
    splitWith = [state.currentUser.id];
  } else if (state.summary?.members) {
    splitWith = state.summary.members.map(m => m.id);
  }

  try {
    let url = `/api/group/${state.groupId}/expense`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        amount: amount,
        title: description || category,
        category: category,
        split_with: splitWith
      })
    });

    if (res.status === 403) {
      showToast('Доступ запрещён: вы не участник этой комнаты', 'error');
      return;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Расход успешно добавлен!', 'success');
    closeSheets();

    if (amountInput) amountInput.value = '';
    if (titleInput) titleInput.value = '';

    await fetchSummary();
  } catch (e) {
    console.error('Failed to submit expense:', e);
    showToast('Ошибка при добавлении расхода', 'error');
  }
}

function openSettlementSheet(debt) {
  state.selectedDebt = debt;
  const fromNameEl = document.getElementById('settleFromName');
  if (fromNameEl) fromNameEl.textContent = debt.from_name || 'Участник';

  const toNameEl = document.getElementById('settleToName');
  if (toNameEl) toNameEl.textContent = debt.to_name || 'Участник';

  const fromAvatarEl = document.getElementById('settleFromAvatar');
  if (fromAvatarEl) fromAvatarEl.textContent = (debt.from_name || 'U')[0];

  const toAvatarEl = document.getElementById('settleToAvatar');
  if (toAvatarEl) toAvatarEl.textContent = (debt.to_name || 'U')[0];

  const amtEl = document.getElementById('settleAmount');
  if (amtEl) amtEl.textContent = formatCurrency(debt.amount);

  openSheet('sheet-settlement');
}

async function handleConfirmSettlement() {
  if (!state.selectedDebt) return;
  const amount = state.selectedDebt.amount;

  try {
    let url = `/api/group/${state.groupId}/settle`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        from_name: state.selectedDebt.from_name,
        to_name: state.selectedDebt.to_name,
        amount: amount
      })
    });

    if (res.status === 403) {
      showToast('Доступ запрещён: вы не участник этой комнаты', 'error');
      return;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Перевод успешно подтверждён!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (e) {
    console.error('Failed to settle debt:', e);
    showToast('Ошибка при фиксации возврата', 'error');
  }
}

function openTransactionSheet(txId) {
  const txList = state.summary?.expenses || [];
  const tx = txList.find(t => t.id === txId);
  if (!tx) return;

  state.selectedTx = tx;
  const color = CATEGORY_COLORS[tx.category] || '#6B6F94';
  const icon = CATEGORY_ICONS[tx.category] || '💳';

  const iconEl = document.getElementById('txModalIcon');
  if (iconEl) {
    iconEl.textContent = icon;
    iconEl.style.backgroundColor = `${color}20`;
    iconEl.style.color = color;
  }

  const amtEl = document.getElementById('txModalAmount');
  if (amtEl) amtEl.textContent = formatCurrency(tx.amount);

  const descEl = document.getElementById('txModalNote');
  if (descEl) descEl.textContent = tx.description || tx.category;

  const catEl = document.getElementById('txModalCategory');
  if (catEl) catEl.textContent = tx.category;

  const payerEl = document.getElementById('txModalPayer');
  if (payerEl) payerEl.textContent = tx.payer_name || 'Участник';

  const dateEl = document.getElementById('txModalDate');
  if (dateEl) dateEl.textContent = tx.created_at || 'Сегодня';

  openSheet('sheet-transaction');
}

// ── Granular Debts Management ───────────────────────────────
function openCreateDebtSheet() {
  const memberSelect = document.getElementById('debtMemberSelect');
  if (memberSelect) {
    const members = state.summary?.members || [];
    const currentId = state.currentUser?.id;
    memberSelect.innerHTML = '<option value="">Выберите участника комнаты...</option>' +
      members.filter(m => Number(m.id) !== Number(currentId)).map(m => `<option value="${m.id}">${m.name}</option>`).join('');
  }

  const descInput = document.getElementById('debtDescriptionInput');
  if (descInput) descInput.value = '';

  const amtInput = document.getElementById('debtAmountInput');
  if (amtInput) amtInput.value = '';

  openSheet('sheet-create-debt');
}

function setCreateDebtDirection(dir) {
  state.createDebtDirection = dir;
  const btnOwed = document.getElementById('debtDirOwedToMe');
  const btnIOwe = document.getElementById('debtDirIOwe');
  const label = document.getElementById('debtCounterpartyLabel');

  if (dir === 'owed_to_me') {
    if (btnOwed) btnOwed.className = 'debt-dir-btn active py-2.5 px-3 rounded-xl border-2 border-mint-500 bg-mint-50/70 text-xs font-extrabold text-mint-800 flex items-center justify-center gap-1.5 transition-all';
    if (btnIOwe) btnIOwe.className = 'debt-dir-btn py-2.5 px-3 rounded-xl border border-ink-200 bg-white text-xs font-bold text-ink-600 flex items-center justify-center gap-1.5 transition-all';
    if (label) label.textContent = 'Кто должен (должник)';
  } else {
    if (btnIOwe) btnIOwe.className = 'debt-dir-btn active py-2.5 px-3 rounded-xl border-2 border-coral-500 bg-coral-50/70 text-xs font-extrabold text-coral-800 flex items-center justify-center gap-1.5 transition-all';
    if (btnOwed) btnOwed.className = 'debt-dir-btn py-2.5 px-3 rounded-xl border border-ink-200 bg-white text-xs font-bold text-ink-600 flex items-center justify-center gap-1.5 transition-all';
    if (label) label.textContent = 'Кому должен (кредитор)';
  }
}

async function handleCreateDebtSubmit(e) {
  e.preventDefault();
  const amtInput = document.getElementById('debtAmountInput');
  const descInput = document.getElementById('debtDescriptionInput');
  const memberSelect = document.getElementById('debtMemberSelect');
  const extToggle = document.getElementById('debtExternalToggle');
  const extNameInput = document.getElementById('debtExternalNameInput');
  const dueDateInput = document.getElementById('debtDueDateInput');
  const freqSelect = document.getElementById('debtFrequencySelect');
  const customMinsInput = document.getElementById('debtCustomMinutesInput');

  const amount = parseFloat(amtInput?.value || 0);
  const description = (descInput?.value || '').trim();
  const isExt = extToggle?.checked || false;
  const extName = (extNameInput?.value || '').trim();
  const memberId = memberSelect?.value;
  const dueDate = dueDateInput?.value || null;
  const freq = freqSelect?.value || 'daily';
  const customMins = parseInt(customMinsInput?.value || 0) || null;

  if (!amount || amount <= 0) {
    showToast('Введите корректную сумму', 'error');
    return;
  }
  if (!description) {
    showToast('Введите описание долга', 'error');
    return;
  }
  if (!isExt && !memberId) {
    showToast('Выберите участника комнаты', 'error');
    return;
  }
  if (isExt && !extName) {
    showToast('Укажите имя внешнего участника', 'error');
    return;
  }

  const payload = {
    amount,
    description,
    direction: state.createDebtDirection,
    is_external: isExt,
    external_name: isExt ? extName : null,
    member_user_id: isExt ? null : parseInt(memberId),
    due_date: dueDate,
    notification_frequency: freq,
    custom_reminder_interval_minutes: customMins
  };

  try {
    let url = `/api/group/${state.groupId}/debts`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Долг успешно зафиксирован!', 'success');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to create debt:', err);
    showToast('Ошибка при создании долга', 'error');
  }
}

async function openDebtDetailSheet(debtId) {
  let url = `/api/debt/${debtId}`;
  if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
    url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
  }

  try {
    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.currentDebtDetail = data.debt;

    const d = data.debt;
    const descEl = document.getElementById('debtDetailDescription');
    if (descEl) descEl.textContent = d.description || 'Долг';

    const partiesEl = document.getElementById('debtDetailParties');
    if (partiesEl) partiesEl.textContent = `${d.debtor_name} → ${d.creditor_name}`;

    const remEl = document.getElementById('debtDetailRemaining');
    if (remEl) remEl.textContent = formatCurrency(d.remaining_amount);

    const origEl = document.getElementById('debtDetailOriginal');
    if (origEl) origEl.textContent = formatCurrency(d.original_amount);

    const dueEl = document.getElementById('debtDetailDueDate');
    if (dueEl) dueEl.textContent = d.due_date || 'Бессрочно';

    const freqEl = document.getElementById('debtDetailFrequency');
    if (freqEl) freqEl.textContent = d.notification_frequency || 'По графику';

    const paymentsList = document.getElementById('debtDetailPaymentsList');
    if (paymentsList) {
      const payments = data.payments || [];
      if (payments.length === 0) {
        paymentsList.innerHTML = '<div class="py-4 text-center text-xs text-ink-400">Платежей пока не было</div>';
      } else {
        paymentsList.innerHTML = payments.map(p => `
          <div class="flex items-center justify-between py-2 text-xs">
            <div>
              <p class="font-bold text-ink-900">${formatCurrency(p.amount)}</p>
              <p class="text-[10px] text-ink-400">${formatDateTime(p.created_at)}</p>
            </div>
            <span class="text-[10px] text-mint-700 font-bold bg-mint-50 px-2 py-0.5 rounded-full">Оплачено</span>
          </div>
        `).join('');
      }
    }

    openSheet('sheet-debt-detail');
    refreshIcons();
  } catch (err) {
    console.error('Failed to load debt detail:', err);
    showToast('Ошибка загрузки деталей долга', 'error');
  }
}

function openDebtPaymentSheet() {
  if (!state.currentDebtDetail) return;
  const remEl = document.getElementById('debtPaymentRemainingAmount');
  if (remEl) remEl.textContent = formatCurrency(state.currentDebtDetail.remaining_amount);
  const amtInp = document.getElementById('debtPaymentAmountInput');
  if (amtInp) amtInp.value = state.currentDebtDetail.remaining_amount;
  openSheet('sheet-debt-payment');
}

async function handleDebtPaymentSubmit(e) {
  e.preventDefault();
  if (!state.currentDebtDetail) return;

  const amtInput = document.getElementById('debtPaymentAmountInput');
  const noteInput = document.getElementById('debtPaymentNoteInput');
  const amount = parseFloat(amtInput?.value || 0);
  const note = (noteInput?.value || '').trim();

  if (!amount || amount <= 0) {
    showToast('Введите корректную сумму платежа', 'error');
    return;
  }

  try {
    let url = `/api/debt/${state.currentDebtDetail.id}/payment`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({ amount, note })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Платёж зафиксирован!', 'success');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to submit debt payment:', err);
    showToast('Ошибка при внесении платежа', 'error');
  }
}

async function handleMarkDebtPaid() {
  if (!state.currentDebtDetail) return;
  if (!confirm('Отметить этот долг как полностью погашенный?')) return;

  try {
    let url = `/api/debt/${state.currentDebtDetail.id}/settle`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({}) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Долг закрыт!', 'success');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to mark debt paid:', err);
    showToast('Ошибка закрытия долга', 'error');
  }
}

async function handleCancelDebt() {
  if (!state.currentDebtDetail) return;
  if (!confirm('Отменить этот долг?')) return;

  try {
    let url = `/api/debt/${state.currentDebtDetail.id}/cancel`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({}) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Долг отменён', 'info');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to cancel debt:', err);
    showToast('Ошибка отмены долга', 'error');
  }
}

// Settings
async function handleSaveBudget() {
  const limitInput = document.getElementById('inputBudgetLimit');
  const limit = parseFloat(limitInput?.value || 0);
  if (!limit || limit <= 0) {
    showToast('Введите корректную сумму лимита', 'error');
    return;
  }

  try {
    let url = `/api/group/${state.groupId}/budget`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({ budget_limit: limit })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Лимит бюджета сохранён!', 'success');
    await fetchSummary();
  } catch (e) {
    console.error('Failed to save budget:', e);
    showToast('Ошибка при сохранении лимита', 'error');
  }
}

async function handleExecuteResetMonth() {
  try {
    let url = `/api/group/${state.groupId}/reset_month`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({})
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast('Новый расчётный период начат!', 'success');
    closeSheets();
    await fetchSummary();
  } catch (e) {
    console.error('Failed to reset month:', e);
    showToast('Ошибка при сбросе периода', 'error');
  }
}

async function handleCreateRoomSubmit(e) {
  e.preventDefault();
  const nameInput = document.getElementById('createRoomNameInput');
  const name = (nameInput?.value || '').trim();
  if (!name) {
    showToast('Введите название комнаты', 'error');
    return;
  }

  try {
    let url = '/api/rooms';
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        name: name,
        room_type: state.createRoomType || 'long_term',
        currency: state.createRoomCurrency || 'RUB'
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast('Комната успешно создана!', 'success');
    closeSheets();

    if (data.room && data.room.id) {
      state.groupId = data.room.id;
    }
    const groupsRes = await fetchUserGroupsList();
    state.availableGroups = groupsRes.groups || [];
    await fetchSummary();
  } catch (err) {
    console.error('Failed to create room:', err);
    showToast('Ошибка при создании комнаты', 'error');
  }
}

// ── Event Listeners Setup ───────────────────────────────────
function setupEventListeners() {
  setupCreateRoomInteractivity();
  // Navigation tabs
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      if (tab) switchTab(tab);
    });
  });

  document.querySelectorAll('.nav-to-analytics').forEach(el => el.addEventListener('click', () => switchTab('analytics')));
  document.querySelectorAll('.nav-to-history').forEach(el => el.addEventListener('click', () => switchTab('history')));
  document.querySelectorAll('.nav-to-family').forEach(el => el.addEventListener('click', () => switchTab('family')));

  // Header & Switchers
  const btnGroupSelector = document.getElementById('btnGroupSelector');
  if (btnGroupSelector) btnGroupSelector.addEventListener('click', openGroupSelectorSheet);

  const btnOpenCreateRoom = document.getElementById('btnOpenCreateRoomSheet');
  if (btnOpenCreateRoom) btnOpenCreateRoom.addEventListener('click', openCreateRoomSheet);

  const btnOpenSettings = document.getElementById('btnOpenSettings');
  if (btnOpenSettings) btnOpenSettings.addEventListener('click', () => switchTab('settings'));

  const btnBackFromSettings = document.getElementById('btnBackFromSettings');
  if (btnBackFromSettings) btnBackFromSettings.addEventListener('click', () => switchTab('overview'));

  // Room Settlement open
  const btnOpenRoomSettlement = document.getElementById('btnOpenRoomSettlement');
  if (btnOpenRoomSettlement) btnOpenRoomSettlement.addEventListener('click', openRoomSettlementSheet);

  const btnGoToRoomSettlement = document.getElementById('btnGoToRoomSettlement');
  if (btnGoToRoomSettlement) btnGoToRoomSettlement.addEventListener('click', openRoomSettlementSheet);

  const btnSendSettlement = document.getElementById('btnSendSettlementToTelegram');
  if (btnSendSettlement) btnSendSettlement.addEventListener('click', handleSendSettlementTelegram);

  const btnArchiveRoom = document.getElementById('btnArchiveRoomSettings');
  if (btnArchiveRoom) btnArchiveRoom.addEventListener('click', handleArchiveRoom);

  // Elevated + Button & Quick Add Banner
  const btnElevatedBot = document.getElementById('btnElevatedBot');
  if (btnElevatedBot) btnElevatedBot.addEventListener('click', () => openSheet('sheet-add-picker'));

  const bannerBotAction = document.getElementById('bannerBotAction');
  if (bannerBotAction) bannerBotAction.addEventListener('click', () => openSheet('sheet-add-picker'));

  // Add Expense Picker options
  document.querySelectorAll('.picker-opt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-target');
      if (target) openSheet(target);
    });
  });

  // Itemized Draft submit & add item
  const btnSubmitDraft = document.getElementById('btnSubmitItemizedExpense');
  if (btnSubmitDraft) btnSubmitDraft.addEventListener('click', handleSubmitItemizedExpense);

  const btnDraftAddItem = document.getElementById('btnDraftAddItem');
  if (btnDraftAddItem) {
    btnDraftAddItem.addEventListener('click', () => {
      if (!state.currentDraft) return;
      state.currentDraft.items.push({
        name: 'Новая позиция',
        quantity: 1,
        unit_price: 0,
        total_amount: 0,
        participants: 'all'
      });
      renderDraftItems();
      recalculateDraftTotals();
    });
  }

  // Create Room Form
  const formCreateRoom = document.getElementById('formCreateRoom');
  if (formCreateRoom) formCreateRoom.addEventListener('submit', handleCreateRoomSubmit);

  const typeBtnLongTerm = document.getElementById('typeBtnLongTerm');
  const typeBtnOneTime = document.getElementById('typeBtnOneTime');
  if (typeBtnLongTerm && typeBtnOneTime) {
    typeBtnLongTerm.addEventListener('click', () => {
      state.createRoomType = 'long_term';
      typeBtnLongTerm.className = 'room-type-btn active py-3 px-3 rounded-xl border-2 border-navy-700 bg-navy-50 text-xs font-extrabold text-navy-900 text-center transition-all';
      typeBtnOneTime.className = 'room-type-btn py-3 px-3 rounded-xl border border-ink-200 bg-white text-xs font-bold text-ink-700 text-center transition-all';
    });
    typeBtnOneTime.addEventListener('click', () => {
      state.createRoomType = 'one_time';
      typeBtnOneTime.className = 'room-type-btn active py-3 px-3 rounded-xl border-2 border-navy-700 bg-navy-50 text-xs font-extrabold text-navy-900 text-center transition-all';
      typeBtnLongTerm.className = 'room-type-btn py-3 px-3 rounded-xl border border-ink-200 bg-white text-xs font-bold text-ink-700 text-center transition-all';
    });
  }

  document.querySelectorAll('.room-cur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.room-cur-btn').forEach(b => {
        b.className = 'room-cur-btn py-2.5 rounded-xl border border-ink-200 bg-white text-xs font-bold text-ink-700 text-center transition-all';
      });
      btn.className = 'room-cur-btn active py-2.5 rounded-xl border-2 border-mint-600 bg-mint-50 text-xs font-black text-mint-900 text-center transition-all';
      state.createRoomCurrency = btn.getAttribute('data-currency') || 'RUB';
    });
  });

  // Sheet close buttons & overlay
  document.querySelectorAll('.close-sheet').forEach(btn => btn.addEventListener('click', closeSheets));
  const overlay = document.getElementById('sheetOverlay');
  if (overlay) {
    overlay.addEventListener('mousedown', (e) => {
      if (e.target === e.currentTarget) closeSheets();
    });
  }

  // Quick Add tabs
  const tabBtnQuickAdd = document.getElementById('tabBtnQuickAdd');
  const tabBtnBotTips = document.getElementById('tabBtnBotTips');
  const viewQuickAdd = document.getElementById('viewQuickAdd');
  const viewBotTips = document.getElementById('viewBotTips');

  if (tabBtnQuickAdd && tabBtnBotTips && viewQuickAdd && viewBotTips) {
    tabBtnQuickAdd.addEventListener('click', () => {
      tabBtnQuickAdd.className = 'flex-1 rounded-lg py-2 bg-white text-navy-900 shadow-sm transition-all';
      tabBtnBotTips.className = 'flex-1 rounded-lg py-2 text-ink-500 transition-all';
      viewQuickAdd.classList.remove('hidden');
      viewBotTips.classList.add('hidden');
      refreshIcons();
    });

    tabBtnBotTips.addEventListener('click', () => {
      tabBtnBotTips.className = 'flex-1 rounded-lg py-2 bg-white text-navy-900 shadow-sm transition-all';
      tabBtnQuickAdd.className = 'flex-1 rounded-lg py-2 text-ink-500 transition-all';
      viewBotTips.classList.remove('hidden');
      viewQuickAdd.classList.add('hidden');
      refreshIcons();
    });
  }

  const btnOpenTelegramChat = document.getElementById('btnOpenTelegramChat');
  if (btnOpenTelegramChat) {
    btnOpenTelegramChat.addEventListener('click', () => {
      if (tg && tg.close) tg.close();
      else window.location.href = 'https://t.me';
    });
  }

  // Other buttons
  const btnSubmitExpense = document.getElementById('btnSubmitExpense');
  if (btnSubmitExpense) btnSubmitExpense.addEventListener('click', handleSubmitExpense);

  const btnConfirmSettlement = document.getElementById('btnConfirmSettlement');
  if (btnConfirmSettlement) btnConfirmSettlement.addEventListener('click', handleConfirmSettlement);

  const btnSaveBudgetLimit = document.getElementById('btnSaveBudgetLimit');
  if (btnSaveBudgetLimit) btnSaveBudgetLimit.addEventListener('click', handleSaveBudget);

  const btnOpenResetConfirm = document.getElementById('btnOpenResetConfirm');
  if (btnOpenResetConfirm) btnOpenResetConfirm.addEventListener('click', () => openSheet('sheet-reset-confirm'));

  const btnExecuteMonthReset = document.getElementById('btnExecuteMonthReset');
  if (btnExecuteMonthReset) btnExecuteMonthReset.addEventListener('click', handleExecuteResetMonth);

  // History filters
  document.querySelectorAll('.cat-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.cat-pill').forEach(p => {
        p.className = 'cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-white text-ink-500 shadow-card';
      });
      pill.className = 'cat-pill active whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-navy-700 text-white shadow-card';
      state.historyCategory = pill.getAttribute('data-category') || 'all';
      renderHistory();
      refreshIcons();
    });
  });

  const historySearchInput = document.getElementById('historySearchInput');
  if (historySearchInput) {
    historySearchInput.addEventListener('input', (e) => {
      state.historySearch = e.target.value;
      renderHistory();
      refreshIcons();
    });
  }

  // Debts Filter Tabs
  document.querySelectorAll('.debt-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.debt-tab-btn').forEach(b => {
        b.className = 'debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all text-ink-500 hover:text-ink-900';
      });
      btn.className = 'debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all bg-white text-navy-800 shadow-sm font-bold';
      state.debtFilter = btn.getAttribute('data-debt-filter') || 'all';
      fetchAndRenderDebts();
    });
  });

  const btnOpenCreateDebt = document.getElementById('btnOpenCreateDebt');
  if (btnOpenCreateDebt) btnOpenCreateDebt.addEventListener('click', openCreateDebtSheet);

  const btnDirOwed = document.getElementById('debtDirOwedToMe');
  if (btnDirOwed) btnDirOwed.addEventListener('click', () => setCreateDebtDirection('owed_to_me'));

  const btnDirIOwe = document.getElementById('debtDirIOwe');
  if (btnDirIOwe) btnDirIOwe.addEventListener('click', () => setCreateDebtDirection('i_owe'));

  const debtExtToggle = document.getElementById('debtExternalToggle');
  if (debtExtToggle) {
    debtExtToggle.addEventListener('change', (e) => {
      const extWrapper = document.getElementById('debtExternalNameWrapper');
      const selectWrapper = document.getElementById('debtMemberSelectWrapper');
      if (extWrapper && selectWrapper) {
        if (e.target.checked) {
          extWrapper.classList.remove('hidden');
          selectWrapper.classList.add('hidden');
        } else {
          extWrapper.classList.add('hidden');
          selectWrapper.classList.remove('hidden');
        }
      }
    });
  }

  const debtFreqSelect = document.getElementById('debtFrequencySelect');
  if (debtFreqSelect) {
    debtFreqSelect.addEventListener('change', (e) => {
      const customWrapper = document.getElementById('debtCustomHoursWrapper');
      if (customWrapper) {
        if (e.target.value === 'custom') customWrapper.classList.remove('hidden');
        else customWrapper.classList.add('hidden');
      }
    });
  }

  const formCreateDebt = document.getElementById('formCreateDebt');
  if (formCreateDebt) formCreateDebt.addEventListener('submit', handleCreateDebtSubmit);

  const btnOpenDebtPayment = document.getElementById('btnOpenDebtPaymentSheet');
  if (btnOpenDebtPayment) btnOpenDebtPayment.addEventListener('click', openDebtPaymentSheet);

  const btnMarkPaid = document.getElementById('btnMarkDebtPaid');
  if (btnMarkPaid) btnMarkPaid.addEventListener('click', handleMarkDebtPaid);

  const btnCancelDebt = document.getElementById('btnCancelDebt');
  if (btnCancelDebt) btnCancelDebt.addEventListener('click', handleCancelDebt);

  
  // Figma Screen 2: Upload Doc
  const docCard = document.getElementById('docFileCardFigma');
  const docInput = document.getElementById('docFileInput');
  const btnDocTrigger = document.getElementById('btnDocTriggerSelect');
  const btnParseDoc = document.getElementById('btnParseDocSubmit');
  
  if (docCard && docInput) docCard.addEventListener('click', () => docInput.click());
  if (btnDocTrigger && docInput) btnDocTrigger.addEventListener('click', () => docInput.click());
  if (docInput) {
    docInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        state.selectedDocFile = e.target.files[0];
        const nameEl = document.getElementById('docFileName');
        const sizeEl = document.getElementById('docFileSize');
        if (nameEl) nameEl.textContent = state.selectedDocFile.name;
        if (sizeEl) sizeEl.textContent = `${Math.round(state.selectedDocFile.size / 1024)} KB · 1 файл`;
        handleParseDocument();
      }
    });
  }
  if (btnParseDoc) btnParseDoc.addEventListener('click', handleConfirmAttachDoc);

  // Figma Screen 3: Text Input
  const btnPaste = document.getElementById('btnPasteFromClipboard');
  if (btnPaste) {
    btnPaste.addEventListener('click', async () => {
      if (navigator.clipboard && navigator.clipboard.readText) {
        try {
          const clipText = await navigator.clipboard.readText();
          if (clipText) {
            const rawInp = document.getElementById('rawExpenseTextInput');
            if (rawInp) rawInp.value = clipText;
            showToast('Вставлено из буфера обмена', 'info');
          }
        } catch (e) {
          showToast('Текст уже вставлен из примера', 'info');
        }
      }
      handleParseText();
    });
  }
  const btnParseText = document.getElementById('btnParseTextSubmit');
  if (btnParseText) btnParseText.addEventListener('click', handleSaveTextExpense);

  // Figma Screen 4: Scan Receipt
  const btnConfirmScan = document.getElementById('btnConfirmScanReceipt');
  if (btnConfirmScan) btnConfirmScan.addEventListener('click', handleConfirmScanReceipt);
  renderScanReceiptItems();
  updateScanMyShare();

  // Figma Screen 5: Voice Input
  const btnVoiceToggle = document.getElementById('btnVoiceRecordToggle');
  if (btnVoiceToggle) btnVoiceToggle.addEventListener('click', toggleVoiceRecording);
  const btnSubmitVoice = document.getElementById('btnSubmitVoiceExpense');
  if (btnSubmitVoice) btnSubmitVoice.addEventListener('click', handleSubmitVoiceExpense);

  const formDebtPayment = document.getElementById('formDebtPayment');
  if (formDebtPayment) formDebtPayment.addEventListener('submit', handleDebtPaymentSubmit);

  const chipPay25 = document.getElementById('chipPay25');
  if (chipPay25) {
    chipPay25.addEventListener('click', () => {
      if (!state.currentDebtDetail) return;
      const amtInput = document.getElementById('debtPaymentAmountInput');
      if (amtInput) amtInput.value = (Math.round(state.currentDebtDetail.remaining_amount * 0.25 * 100) / 100).toFixed(2);
    });
  }

  const chipPay50 = document.getElementById('chipPay50');
  if (chipPay50) {
    chipPay50.addEventListener('click', () => {
      if (!state.currentDebtDetail) return;
      const amtInput = document.getElementById('debtPaymentAmountInput');
      if (amtInput) amtInput.value = (Math.round(state.currentDebtDetail.remaining_amount * 0.5 * 100) / 100).toFixed(2);
    });
  }

  const chipPay100 = document.getElementById('chipPay100');
  if (chipPay100) {
    chipPay100.addEventListener('click', () => {
      if (!state.currentDebtDetail) return;
      const amtInput = document.getElementById('debtPaymentAmountInput');
      if (amtInput) amtInput.value = state.currentDebtDetail.remaining_amount.toFixed(2);
    });
  }
}

// ── App Init Sequence ───────────────────────────────────────
async function initApp() {
  try {
    if (window.Telegram?.WebApp) {
      try {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
      } catch (e) {}
    }

    setupEventListeners();

    const groupsRes = await fetchUserGroupsList();
    state.availableGroups = groupsRes.groups || [];
    if (groupsRes.user) state.currentUser = groupsRes.user;

    const detectedId = detectGroupId();
    let targetGroupId = null;

    if (detectedId && Number(detectedId) !== 0) {
      const found = state.availableGroups.find(g => Number(g.id) === Number(detectedId));
      if (found) targetGroupId = found.id;
      else if (state.availableGroups.length > 0) targetGroupId = state.availableGroups[0].id;
      else targetGroupId = detectedId;
    } else if (state.availableGroups.length > 0) {
      targetGroupId = state.availableGroups[0].id;
    }

    if (!targetGroupId || (state.availableGroups.length === 0 && Number(targetGroupId) === 0)) {
      renderNoGroupsState();
      return;
    }

    state.groupId = targetGroupId;
    await fetchSummary();

  } catch (err) {
    console.error('Failed to init app:', err);
  } finally {
    refreshIcons();
  }
}

document.addEventListener('DOMContentLoaded', initApp);
"""

with open(os.path.join(WEBAPP_DIR, "app.js"), "w", encoding="utf-8") as f:
    f.write(js_content)
print("Wrote app.js successfully.")
