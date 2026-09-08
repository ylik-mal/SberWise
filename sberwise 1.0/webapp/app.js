/**
 * СберСплит — Telegram Mini App (Modern Navy/Mint Design)
 * Кейс 3: Платформа Комнат (Room Concept) + Мульти-ввод и интерактивный сплит чеков
 */

const tg = window.Telegram?.WebApp;
let telegramReadyCalled = false;
let telegramBackButtonBound = false;
function initializeTelegramWebApp() {
  if (!tg || telegramReadyCalled) return;
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor('#0E1422');
    if (tg.setBackgroundColor) tg.setBackgroundColor('#0B0F19');
    telegramReadyCalled = true;
  } catch (e) {
    console.warn('Telegram WebApp init warning:', e);
  }
}
initializeTelegramWebApp();

const APP_VERSION = "2.4.0-prod";
let appListenersReady = false;
const bootDebug = { appMount: 'WAIT', telegram: 'WAIT', initData: 'NO', auth: 'WAIT', rooms: 'WAIT', launchMode: 'unknown', route: location.pathname, loaderReason: 'starting', lastError: '', apiUrl: location.host };
function updateBootDebug(patch = {}) {
  Object.assign(bootDebug, patch);
  if (!new URLSearchParams(location.search).has('debug')) return;
  let panel = document.getElementById('bootDebugPanel');
  if (!panel) { panel = document.createElement('pre'); panel.id = 'bootDebugPanel'; panel.style.cssText = 'position:fixed;right:8px;bottom:calc(88px + env(safe-area-inset-bottom));z-index:9999;max-width:calc(100vw - 16px);padding:10px;border-radius:10px;background:rgba(3,8,18,.92);color:#9fffd8;font:10px/1.35 monospace;white-space:pre-wrap;pointer-events:none'; document.body.appendChild(panel); }
  panel.textContent = Object.entries(bootDebug).map(([k,v]) => `${k.toUpperCase()}: ${v || '—'}`).join('\n');
}

function showNetworkRecovery(title, message) {
  const overlay = document.getElementById('networkRecoveryOverlay');
  const titleEl = document.getElementById('networkRecoveryTitle');
  const messageEl = document.getElementById('networkRecoveryMessage');
  if (titleEl) titleEl.textContent = title || 'Не удалось подключиться к серверу';
  if (messageEl) messageEl.textContent = message || 'Проверьте подключение к интернету. Если сервер только запускается, повторите попытку через несколько секунд.';
  if (overlay) overlay.classList.remove('hidden');
}

function hideNetworkRecovery() {
  const overlay = document.getElementById('networkRecoveryOverlay');
  if (overlay) overlay.classList.add('hidden');
}

function showGlobalErrorBanner(msg) {
  const banner = document.getElementById('globalErrorBanner');
  const txt = document.getElementById('globalErrorText');
  if (banner && txt) {
    txt.textContent = msg || 'Произошла непредвиденная ошибка';
    banner.classList.remove('hidden');
  }
}

// Global Error Handlers (Section 25)
window.addEventListener('error', (event) => {
  console.error('[Global Error]', event.error || event.message);
  showGlobalErrorBanner(event.message || 'Ошибка выполнения приложения');
  updateBootDebug({ lastError: event.message || 'runtime error', loaderReason: 'runtime_error' });
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise Rejection]', event.reason);
  updateBootDebug({ lastError: String(event.reason || 'promise rejection'), loaderReason: 'runtime_error' });
});

// Safe fetch with retries for safe GET calls and timeouts (Sections 23, 26, 27)
async function safeFetch(url, options = {}, retries = 2, timeoutMs = 15000) {
  const method = (options.method || 'GET').toUpperCase();
  const isSafeMethod = method === 'GET' || method === 'HEAD';
  const effectiveRetries = isSafeMethod ? retries : 0; // Не retry POST/PUT/DELETE автоматически (Section 27)

  for (let attempt = 0; attempt <= effectiveRetries; attempt++) {
    const controller = new AbortController();
    lifecycle.pendingRequests.add(controller);
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const fetchOpts = {
        ...options,
        signal: controller.signal
      };
      const res = await fetch(url, fetchOpts);
      clearTimeout(timeoutId);
      lifecycle.pendingRequests.delete(controller);

      // Если получили ответ сервера, сеть работает -> скрываем плашку
      hideNetworkRecovery();

      // Для безопасных GET при 502/503/504 можно повторить
      if (isSafeMethod && (res.status === 502 || res.status === 503 || res.status === 504) && attempt < effectiveRetries) {
        const delay = (attempt + 1) * 750;
        await new Promise(r => setTimeout(r, delay));
        continue;
      }

      return res;
    } catch (err) {
      clearTimeout(timeoutId);
      lifecycle.pendingRequests.delete(controller);
      const isAbort = err.name === 'AbortError';
      const isLastAttempt = attempt >= effectiveRetries;

      if (lifecycle.suspended) throw err;

      console.warn(`[safeFetch] attempt ${attempt + 1}/${effectiveRetries + 1} failed for ${url}:`, err.message);

      if (isLastAttempt) {
        if (isSafeMethod) {
          showNetworkRecovery();
        }
        throw new Error(isAbort ? 'Превышено время ожидания ответа сервера (таймаут)' : 'Ошибка сети: сервер недоступен');
      }

      const delay = (attempt + 1) * 750;
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

// Category palette mapping
const CATEGORY_COLORS = {
  '🍞 Продукты': '#F59E0B',
  'Продукты': '#F59E0B',
  '🚗 Транспорт': '#4F8CFF',
  'Транспорт': '#4F8CFF',
  '🏠 Жильё': '#20C997',
  'Жильё': '#20C997',
  '☕ Кафе': '#FF8A3D',
  'Кафе': '#FF8A3D',
  '🎉 Развлечения': '#B16CFF',
  'Развлечения': '#B16CFF',
  '💊 Аптека': '#FF5C7A',
  'Аптека': '#FF5C7A',
  'Техника': '#A855F7', 'Электроника': '#A855F7',
  'Коммуналка': '#20C997', 'Аренда': '#20C997',
  'Здоровье': '#FF5C7A', 'Одежда': '#E879F9',
  'Образование': '#84CC16', 'Связь': '#22D3EE',
  'Поездки': '#22D3EE',
  '🔧 Другое': '#94A3B8',
  'Другое': '#94A3B8'
};

// Distinct fallback colors keep adjacent chart segments visually separable,
// including categories introduced by newer server versions.
const CATEGORY_PALETTE = [
  '#F59E0B', '#20C997', '#4F8CFF', '#B16CFF', '#FF5C7A',
  '#22D3EE', '#FF8A3D', '#84CC16', '#E879F9', '#94A3B8'
];

const CATEGORY_ICONS = {
  '🍞 Продукты': 'shopping-basket', 'Продукты': 'shopping-basket',
  '🚗 Транспорт': 'car-front', 'Транспорт': 'car-front',
  '🏠 Жильё': 'house', 'Жильё': 'house', 'Дом': 'house', 'Дом / Быт': 'house',
  '☕ Кафе': 'coffee', 'Кафе': 'coffee', 'Кафе / Рестораны': 'utensils',
  '🎉 Развлечения': 'ticket', 'Развлечения': 'ticket',
  '💊 Аптека': 'pill', 'Аптека': 'pill', 'Здоровье': 'heart-pulse',
  'Одежда': 'shirt', 'Связь': 'smartphone', 'Интернет': 'wifi',
  'Подписки': 'repeat-2', 'Путешествия': 'plane', 'Подарки': 'gift',
  'Образование': 'book-open', 'Красота': 'sparkles', 'Спорт': 'dumbbell',
  'Техника': 'laptop', 'Электроника': 'laptop', 'Игровые устройства': 'gamepad-2', 'Коммуналка': 'lamp-desk', 'Аренда': 'house',
  '🔧 Другое': 'tag', 'Другое': 'tag'
};

function getCategoryIcon(category, className = 'category-icon') {
  const raw = String(category || '').trim();
  const normalized = getCategoryLabel(raw);
  const canonical = canonicalCategoryName(raw);
  const icon = CATEGORY_ICONS[raw] || CATEGORY_ICONS[normalized] || CATEGORY_ICONS[canonical] || 'tag';
  return `<i data-lucide="${icon}" class="${className}" aria-hidden="true"></i>`;
}

// Presentation-only merchant mapping. Stored purchases stay untouched; every renderer
// resolves a local asset from the title/merchant when it is known.
const MERCHANT_LOGOS = [
  { id: 'magnit', asset: 'magnit.svg', aliases: ['магнит', 'магнит у дома', 'ао тандер', 'magnit'] },
  { id: 'pyaterochka', asset: 'pyaterochka.svg', aliases: ['пятёрочка', 'пятерочка', 'pyaterochka'] },
  { id: 'perekrestok', asset: 'perekrestok.svg', aliases: ['перекрёсток', 'перекресток', 'perekrestok'] },
  { id: 'lenta', asset: 'lenta.svg', aliases: ['лента', 'супермаркет лента', 'lenta'] },
  { id: 'ozon', asset: 'ozon.svg', aliases: ['ozon', 'озон'] },
  { id: 'wildberries', asset: 'wildberries.svg', aliases: ['wildberries', 'вайлдберриз', 'wb'] },
  { id: 'yandex-market', asset: 'yandex-market.svg', aliases: ['яндекс маркет', 'yandex market'] },
  { id: 'yandex-go', asset: 'yandex-go.svg', aliases: ['яндекс go', 'яндекс такси', 'yandex go', 'yandex taxi'] },
  { id: 'samokat', asset: 'samokat.svg', aliases: ['самокат', 'samokat'] },
  { id: 'dns', asset: 'dns.svg', aliases: ['dns', 'днс'] },
  { id: 'mvideo', asset: 'mvideo.svg', aliases: ['м.видео', 'м видео', 'mvideo', 'm.video'] },
  { id: 'spar', asset: 'spar.svg', aliases: ['spar', 'спар'] }
];

function normalizeMerchantName(value) {
  return String(value || '')
    .toLocaleLowerCase('ru-RU')
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getMerchantLogo(merchantName) {
  const name = normalizeMerchantName(merchantName);
  if (!name) return null;
  return MERCHANT_LOGOS.find(merchant => merchant.aliases.some(alias => {
    const normalizedAlias = normalizeMerchantName(alias);
    return name === normalizedAlias || name.includes(normalizedAlias);
  })) || null;
}

function getMerchantIcon(merchantName, category, className = 'category-icon') {
  const merchant = getMerchantLogo(merchantName);
  if (!merchant) return getCategoryIcon(category, className);
  const alt = escapeHtml(merchant.id);
  return `<span class="merchant-icon merchant-icon--${merchant.id}"><img class="merchant-logo-image" src="assets/merchants/${merchant.asset}" alt="${alt}" loading="lazy" onerror="this.classList.add('is-broken')"><span class="merchant-icon-fallback">${getCategoryIcon(category, className)}</span></span>`;
}

// Legacy emoji prefixes remain in stored data but are hidden in rendered labels.
function getCategoryLabel(category, fallback = 'Другое') {
  const raw = String(category || '').trim();
  return raw.replace(/^[^\p{L}\p{N}]+/u, '').trim() || fallback;
}

function getTransactionDisplayTitle(tx, fallback = 'Покупка') {
  const genericWebApp = /^расход\s+из\s+webapp$/i.test(String(tx?.description || '').trim());
  if (tx?.title && !genericWebApp) return tx.title;
  if (tx?.description && !genericWebApp) return tx.description;
  return getCategoryLabel(tx?.category, fallback);
}

const CATEGORY_CANONICAL_NAMES = Object.freeze({
  'продукты': 'Продукты', 'продукты питания': 'Продукты', 'еда': 'Продукты', 'напитки': 'Продукты', 'супермаркет': 'Продукты',
  'транспорт': 'Транспорт', 'такси': 'Транспорт', 'поездки': 'Транспорт', 'бензин': 'Транспорт', 'авто': 'Транспорт',
  'жилье': 'Жильё', 'аренда': 'Жильё', 'коммуналка': 'Жильё', 'дом': 'Жильё', 'дом быт': 'Жильё',
  'кафе': 'Кафе', 'кафе рестораны': 'Кафе', 'кафе и рестораны': 'Кафе', 'рестораны': 'Кафе',
  'развлечения': 'Развлечения', 'досуг': 'Развлечения',
  'аптека': 'Аптека', 'здоровье': 'Аптека', 'медицина': 'Аптека',
  'техника': 'Техника', 'электроника': 'Техника',
  'одежда': 'Одежда', 'образование': 'Образование',
  'связь': 'Связь', 'интернет': 'Связь',
  'другое': 'Другое', 'прочее': 'Другое', 'other': 'Другое'
});

function canonicalCategoryName(category) {
  const label = getCategoryLabel(category);
  const key = label.toLocaleLowerCase('ru-RU').replace(/ё/g, 'е').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  return CATEGORY_CANONICAL_NAMES[key] || label;
}

// Categories in the database may contain a legacy emoji ("🔧 Другое"),
// different letter case, or a more specific category which has no own pill.
// History filters work with normalized labels rather than the raw DB value.
function getHistoryCategoryKey(category) {
  return canonicalCategoryName(category)
    .toLocaleLowerCase('ru-RU')
    .replace(/ё/g, 'е')
    .trim();
}

const HISTORY_PILL_CATEGORY_KEYS = new Set([
  'продукты', 'транспорт', 'жилье', 'кафе', 'развлечения', 'аптека', 'другое'
]);

function matchesHistoryCategory(category, selectedCategory) {
  if (!selectedCategory || selectedCategory === 'all') return true;

  const actual = getHistoryCategoryKey(category);
  const selected = getHistoryCategoryKey(selectedCategory);
  if (selected !== 'другое') return actual === selected;

  // «Другое» combines explicit legacy/default values and categories that do
  // not have a dedicated history filter, so no expense becomes unreachable.
  return actual === 'другое' || actual === 'прочее' || actual === 'other'
    || !HISTORY_PILL_CATEGORY_KEYS.has(actual);
}

function getCategoryColor(category, index = 0) {
  const canonical = canonicalCategoryName(category);
  if (CATEGORY_COLORS[canonical]) return CATEGORY_COLORS[canonical];
  const raw = String(canonical || 'Другое');
  const hash = [...raw].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 0);
  return CATEGORY_PALETTE[(hash + index) % CATEGORY_PALETTE.length];
}

function mergeCategoryEntries(categories = []) {
  const merged = new Map();
  categories.forEach(item => {
    const name = canonicalCategoryName(item.category);
    const current = merged.get(name) || { ...item, category: name, amount: 0 };
    current.amount = Number(current.amount || 0) + Number(item.amount || 0);
    merged.set(name, current);
  });
  const total = [...merged.values()].reduce((sum, item) => sum + item.amount, 0);
  return [...merged.values()].map(item => ({ ...item, percent: total ? Math.round((item.amount / total) * 1000) / 10 : 0 }));
}

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
  historyDate: '',
  historyExpenses: null,
  historyExpensesGroupId: null,
  historyLoading: false,
  selectedDebt: null,
  isConfirmingSettlement: false,
  settlementRequestId: null,
  selectedTx: null,
  debtFilter: 'all',
  currentDebtDetail: null,
  createDebtDirection: 'owed_to_me',
  isCreatingDebt: false,
  debtCreateRequestId: null,
  isSubmittingDebtPayment: false,
  debtPaymentRequestId: null,
  isTelegramMemberPickerPending: false,
  telegramMemberPickerRequestId: null,
  telegramMemberPickerPoll: null,
  debtsList: [],
  debtsSummary: null,
  
  // Room platform additions:
  currentDraft: null,
  roomSettlement: null,
  isOpeningRoomSettlement: false,
  createRoomType: 'long_term',
  createRoomCurrency: 'RUB',
  mediaRecorder: null,
  audioChunks: [],
  voiceRecordInterval: null,
  voiceRecordSeconds: 0,
  selectedReceiptFile: null,
  selectedDocFile: null,
  parsedDocumentDraft: null,
  documentParticipantIds: [],

  // Navigation architecture
  activeInputMode: null,
  activeSheet: null,
  settingsReturnTab: 'overview',
  notificationsOpen: false,
  textExpenseDraft: '',

  // Real Analytics Architecture
  analyticsPeriod: {
    type: 'current_month',
    from: null,
    to: null
  },
  analyticsData: null,
  analyticsLoading: false,
  selectedRoomDonutCategory: null
};

let donutChartInstance = null;
let weeklyChartInstance = null;
let analyticsDonutChartInstance = null;
// SberWise's restrained emerald / teal / cyan / blue palette. Gradients add
// depth at draw-time, while these base tones keep the legend in sync.
const ANALYTICS_DONUT_PALETTE = ['#16CFA5', '#13BFAE', '#159CA5', '#2B7E9F', '#3A668C'];

function mixAnalyticsDonutColor(from, to, amount) {
  const parse = hex => hex.match(/[a-f\d]{2}/gi).map(part => parseInt(part, 16));
  const [fr, fg, fb] = parse(from);
  const [tr, tg, tb] = parse(to);
  const mix = (source, target) => Math.round(source + (target - source) * amount);
  return `rgb(${mix(fr, tr)}, ${mix(fg, tg)}, ${mix(fb, tb)})`;
}

function createAnalyticsDonutGradient(context, baseColor) {
  const { chart, dataIndex } = context;
  const area = chart.chartArea;
  if (!area || !chart.ctx || dataIndex == null) return baseColor;
  const centerX = (area.left + area.right) / 2;
  const centerY = (area.top + area.bottom) / 2;
  const outerRadius = Math.min(area.right - area.left, area.bottom - area.top) / 2;
  const gradient = chart.ctx.createRadialGradient(centerX, centerY, outerRadius * 0.53, centerX, centerY, outerRadius);
  gradient.addColorStop(0, mixAnalyticsDonutColor(baseColor, '#C6FFF1', 0.18));
  gradient.addColorStop(0.58, baseColor);
  gradient.addColorStop(1, mixAnalyticsDonutColor(baseColor, '#052B35', 0.34));
  return gradient;
}

function renderAnalyticsDonutTooltip(tooltipContext, categories, currency, stageSelector = '.analytics-donut-stage') {
  const stage = document.querySelector(stageSelector);
  if (!stage) return;
  let tooltipEl = stage.querySelector('.expense-donut-tooltip');
  if (!tooltipEl) {
    tooltipEl = document.createElement('div');
    tooltipEl.className = 'expense-donut-tooltip';
    tooltipEl.setAttribute('role', 'status');
    stage.appendChild(tooltipEl);
  }

  const tooltip = tooltipContext.tooltip;
  const point = tooltip?.dataPoints?.[0];
  const item = point ? categories[point.dataIndex] : null;
  if (!tooltip || !tooltip.opacity || !item || !Number.isFinite(item.amount)) {
    tooltipEl.classList.remove('is-visible');
    return;
  }

  tooltipEl.innerHTML = `<strong>${escapeHtml(getCategoryLabel(item.category))}</strong><span>${formatCurrency(item.amount, currency)} <i>·</i> ${item.percent}%</span>`;
  tooltipEl.classList.add('is-visible');

  const width = Math.min(tooltipEl.offsetWidth || 156, stage.clientWidth - 16);
  const height = tooltipEl.offsetHeight || 58;
  const centerX = stage.clientWidth / 2;
  const centerY = stage.clientHeight / 2;
  const dx = tooltip.caretX - centerX;
  const dy = tooltip.caretY - centerY;
  const length = Math.max(Math.hypot(dx, dy), 1);
  const offset = 31;
  const anchorX = tooltip.caretX + (dx / length) * offset;
  const anchorY = tooltip.caretY + (dy / length) * offset;
  const clamp = (value, min, max) => Math.max(min, Math.min(value, max));
  const left = clamp(anchorX - width / 2, 8, stage.clientWidth - width - 8);
  const top = clamp(anchorY - height / 2, 8, stage.clientHeight - height - 8);
  tooltipEl.style.left = `${left}px`;
  tooltipEl.style.top = `${top}px`;
}

function isTouchDonutInteraction() {
  return Boolean(window.matchMedia?.('(hover: none), (pointer: coarse)')?.matches);
}

function renderRoomDonutDetail(item, currency = 'RUB') {
  const detail = document.getElementById('roomDonutDetail');
  if (!detail) return;
  if (!item) {
    detail.classList.remove('is-selected');
    detail.innerHTML = '';
    return;
  }
  detail.innerHTML = `<span class="room-donut-detail-icon" style="color:${item.color}">${getCategoryIcon(item.category)}</span><div><strong>${escapeHtml(getCategoryLabel(item.category))}</strong><span>${formatCurrency(item.amount, currency)} <i>·</i> ${item.percent}%</span></div><button type="button" class="room-donut-detail-close" aria-label="Закрыть детали">×</button>`;
  detail.classList.add('is-selected');
  // Detail markup is inserted after the main screen render; turn the same
  // data-lucide element used by the legend into its SVG counterpart.
  refreshIcons();
  detail.querySelector('.room-donut-detail-close')?.addEventListener('click', () => {
    state.selectedRoomDonutCategory = null;
    renderRoomDonutDetail(null, currency);
  }, { once: true });
}

function createExpenseDonutChart({ canvas, categories, currency = 'RUB', isEmpty = false, compact = false, tooltipStageSelector, onSegmentTap = null }) {
  const ctx = canvas.getContext('2d');
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: isEmpty ? ['Пока нет расходов'] : categories.map(item => getCategoryLabel(item.category)),
      datasets: [{
        data: isEmpty ? [1] : categories.map(item => item.amount),
        backgroundColor: isEmpty ? ['#173943'] : context => createAnalyticsDonutGradient(context, categories[context.dataIndex]?.color || '#159CA5'),
        borderColor: 'rgba(2,28,38,.94)',
        borderWidth: isEmpty ? 0 : 2.5,
        borderRadius: isEmpty ? 0 : (compact ? 6 : 9),
        spacing: isEmpty ? 0 : 3,
        hoverOffset: isEmpty ? 0 : (compact ? 3 : 6),
        hoverBorderWidth: isEmpty ? 0 : 2,
        cutout: compact ? '66%' : '62%',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 420 },
      interaction: { mode: 'nearest', intersect: true },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: false,
          external: context => {
            if (compact && isTouchDonutInteraction()) {
              document.querySelector(`${tooltipStageSelector} .expense-donut-tooltip`)?.classList.remove('is-visible');
              return;
            }
            renderAnalyticsDonutTooltip(context, categories, currency, tooltipStageSelector);
          },
        },
      },
      onClick: (event, elements) => {
        if (!compact || !isTouchDonutInteraction() || !onSegmentTap) return;
        onSegmentTap(elements?.[0] ? categories[elements[0].index] : null);
      },
    },
  });
}

// ── Mini App lifecycle ──────────────────────────────────────
// Mobile WebViews can freeze timers and requests while the phone is locked.  This
// controller keeps a ready app separate from cold boot and repairs it once on resume.
const lifecycle = {
  phase: 'BOOTING',
  suspended: false,
  backgroundedAt: 0,
  resumeInProgress: false,
  lastResumeAt: 0,
  resumeTimer: null,
  listenersReady: false,
  resumeAttempts: 0,
  pendingRequests: new Set(),
};
const RESUME_REFRESH_AFTER_MS = 2500;
const RESUME_DEBOUNCE_MS = 900;

function lifecycleDebug(event, extra = {}) {
  if (!new URLSearchParams(location.search).has('debug')) return;
  console.debug(`[${event}]`, { durationMs: extra.durationMs || 0, tab: state.currentTab, sheet: state.activeSheet || null, attempts: lifecycle.resumeAttempts, ...extra });
}

function abortStaleRequests() {
  lifecycle.pendingRequests.forEach(controller => {
    try { controller.abort(); } catch (e) {}
  });
  lifecycle.pendingRequests.clear();
}

function repairTransientUi() {
  const overlay = document.getElementById('sheetOverlay');
  const activeSheet = state.activeSheet && document.getElementById(state.activeSheet);
  const activeSheetIsUsable = activeSheet && !activeSheet.classList.contains('hidden');
  if (!activeSheetIsUsable && !state.notificationsOpen) {
    state.activeSheet = null;
    overlay?.classList.remove('active');
    overlay?.classList.add('hidden');
    document.querySelectorAll('.sheet-content.active.hidden').forEach(sheet => sheet.classList.remove('active'));
  }
  const appShell = document.getElementById('appShell');
  if (appShell?.style.pointerEvents === 'none') appShell.style.pointerEvents = '';
  if (document.body.style.pointerEvents === 'none') document.body.style.pointerEvents = '';
  if (!state.activeInputMode && document.body.style.overflow === 'hidden') document.body.style.overflow = '';
  if (lifecycle.phase === 'READY') document.body.classList.remove('startup-pending');
}

function restoreReceiptScannerAfterResume() {
  if (!state.scannerNeedsReopen || state.activeInputMode !== 'receipt') return;
  state.scannerNeedsReopen = false;
  showScanError(
    'Камера была приостановлена',
    'Telegram остановил камеру в фоне. Нажмите «Попробовать снова», чтобы безопасно открыть её повторно.',
    'CAMERA_REOPEN_REQUIRED'
  );
}

function resizeChartsAfterResume() {
  requestAnimationFrame(() => {
    try { donutChartInstance?.resize(); } catch (e) {}
    try { weeklyChartInstance?.resize(); } catch (e) {}
    try { analyticsDonutChartInstance?.resize(); } catch (e) {}
  });
}

function handleAppSuspend(source = 'visibilitychange') {
  if (lifecycle.suspended) return;
  lifecycle.suspended = true;
  lifecycle.backgroundedAt = Date.now();
  if (lifecycle.phase === 'READY') lifecycle.phase = 'SUSPENDED';
  abortStaleRequests();
  // Camera/microphone sessions are a common source of a stuck Android WebView.
  state.scannerNeedsReopen = state.activeInputMode === 'receipt' && Boolean(state.activeCameraStream);
  stopReceiptCamera();
  stopVoiceMicrophone();
  lifecycleDebug('APP_BACKGROUND', { source });
}

function scheduleAppResume(source = 'focus', force = false) {
  if (document.hidden) return;
  if (lifecycle.resumeTimer) clearTimeout(lifecycle.resumeTimer);
  lifecycle.resumeTimer = setTimeout(() => {
    lifecycle.resumeTimer = null;
    void handleAppResume(source, force);
  }, 80);
}

async function handleAppResume(source = 'visibilitychange', force = false) {
  if (document.hidden || lifecycle.resumeInProgress) return;
  const now = Date.now();
  const durationMs = lifecycle.backgroundedAt ? now - lifecycle.backgroundedAt : 0;
  const needsRefresh = force || lifecycle.suspended && durationMs >= RESUME_REFRESH_AFTER_MS;
  if (lifecycle.phase !== 'SUSPENDED' && lifecycle.phase !== 'READY') return;
  if (!needsRefresh) {
    lifecycle.suspended = false;
    lifecycle.backgroundedAt = 0;
    repairTransientUi();
    restoreReceiptScannerAfterResume();
    return;
  }
  if (now - lifecycle.lastResumeAt < RESUME_DEBOUNCE_MS) return;

  lifecycle.resumeInProgress = true;
  lifecycle.lastResumeAt = now;
  lifecycle.phase = 'RESUMING';
  lifecycle.resumeAttempts += 1;
  lifecycleDebug('RESUME_START', { source, durationMs });
  try {
    const health = await safeFetch('/api/health', { headers: getRequestHeaders() }, 0, 7000);
    if (!health.ok) throw new Error(`Health check failed (${health.status})`);
    if (state.groupId) await fetchSummary();
    if (state.currentTab === 'analytics') await fetchAnalytics();
    await refreshNotificationBadge();
    repairTransientUi();
    restoreReceiptScannerAfterResume();
    resizeChartsAfterResume();
    hideNetworkRecovery();
    lifecycleDebug('RESUME_DONE', { source, durationMs });
  } catch (error) {
    showNetworkRecovery();
    lifecycleDebug('RESUME_FAILED', { source, durationMs, error: error?.message || String(error) });
  } finally {
    lifecycle.suspended = false;
    lifecycle.backgroundedAt = 0;
    lifecycle.resumeInProgress = false;
    lifecycle.phase = 'READY';
  }
}

function setupLifecycleController() {
  if (lifecycle.listenersReady) return;
  lifecycle.listenersReady = true;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) handleAppSuspend('visibilitychange');
    else scheduleAppResume('visibilitychange');
  });
  window.addEventListener('focus', () => scheduleAppResume('focus'));
  window.addEventListener('pageshow', () => scheduleAppResume('pageshow'));
  window.addEventListener('pagehide', () => handleAppSuspend('pagehide'));
  window.addEventListener('offline', () => {
    showNetworkRecovery();
    lifecycleDebug('APP_OFFLINE');
  });
  window.addEventListener('online', () => scheduleAppResume('online', true));
  try {
    tg?.onEvent?.('activated', () => scheduleAppResume('telegram_activated'));
    tg?.onEvent?.('deactivated', () => handleAppSuspend('telegram_deactivated'));
  } catch (e) {}
}

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

// Room format is a persisted backend field (groups.type), never a guess based
// on the room's name or a fallback visual label.
function isOneTimeRoom(room) {
  return room?.room_type === 'one_time' || room?.type === 'one_time';
}

function getRoomTypeLabel(room) {
  return isOneTimeRoom(room) ? 'Разовая' : 'Длительная';
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

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getRequestHeaders(isMultipart = false) {
  const headers = {};
  if (!isMultipart) {
    headers['Content-Type'] = 'application/json';
  }
  if (tg && tg.initData) {
    headers['X-Telegram-Init-Data'] = tg.initData;
  }
  return headers;
}

function appendTgUserId(url) {
  const localTestUserId = (location.hostname === '127.0.0.1' || location.hostname === 'localhost')
    ? new URLSearchParams(location.search).get('tg_user_id')
    : null;
  const userId = tg?.initDataUnsafe?.user?.id || localTestUserId;
  if (userId) {
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}tg_user_id=${encodeURIComponent(userId)}`;
  }
  return url;
}

// Group ID Extraction
function detectGroupId() {
  const urlParams = new URLSearchParams(window.location.search);
  const qId = urlParams.get('group_id') || urlParams.get('gid') || urlParams.get('room_id');
  if (qId && Number(qId) !== 0) return Number(qId);

  if (window.location.hash) {
    try {
      const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''));
      const hId = hashParams.get('group_id') || hashParams.get('gid') || hashParams.get('room_id');
      if (hId && Number(hId) !== 0) return Number(hId);
    } catch (e) {}
  }

  if (tg && tg.initDataUnsafe?.start_param) {
    const sp = String(tg.initDataUnsafe.start_param);
    if (sp.startsWith('group_')) return Number(sp.replace('group_', '')) || 0;
    if (sp.startsWith('room_')) return Number(sp.replace('room_', '')) || 0;
    if (sp.startsWith('app_')) return Number(sp.replace('app_', '')) || 0;
    const parsed = Number(sp);
    if (!isNaN(parsed) && parsed !== 0) return parsed;
  }
  return 0;
}

// ── Debts Data Fetching ──────────────────────────────────────
async function fetchGroupDebts(groupId, filterTab = 'all') {
  if (!groupId) return null;
  let url = appendTgUserId(`/api/group/${groupId}/debts?tab=${filterTab}`);
  try {
    const res = await safeFetch(url, { headers: getRequestHeaders() }, 1, 12000);
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error('Network error fetching debts', err);
    throw err;
  }
}

// ── Data Fetching ───────────────────────────────────────────
async function fetchUserGroupsList() {
  try {
    const url = appendTgUserId('/api/groups');
    const res = await safeFetch(url, { headers: getRequestHeaders() }, 2, 10000);
    if (!res.ok) return { groups: [], user: null, requestFailed: true };
    return await res.json();
  } catch (e) {
    console.error('Error in fetchUserGroupsList:', e);
    return { groups: [], user: null, requestFailed: true };
  }
}

async function fetchSummary() {
  if (!state.groupId && state.groupId !== 0) return;
  
  let url = appendTgUserId(`/api/group/${state.groupId}/summary`);

  let data;
  try {
    const res = await safeFetch(url, { headers: getRequestHeaders() }, 2, 15000);

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
  // Never mix the transaction history of a previous room with this one.
  if (Number(state.historyExpensesGroupId) !== Number(state.groupId)) {
    state.historyExpenses = null;
    state.historyExpensesGroupId = null;
  }
  if (data.available_groups && data.available_groups.length > 0) {
    state.availableGroups = data.available_groups;
  }
  if (data.current_user) {
    state.currentUser = data.current_user;
  }

  console.log('[DASHBOARD_SUCCESS]', {
    groupId: data.group_id,
    groupName: data.group_name,
    totalExpenses: data.total_expenses
  });
  if (data.budget) console.log('[BUDGET_SUCCESS]', { target: data.budget.target_budget, status: data.budget.status });
  if (data.simplified_debts) console.log('[SETTLEMENT_SUCCESS]', { count: data.simplified_debts.length });

  try {
    renderAll();
    fetchAnalytics();
    void refreshNotificationBadge();
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

  const room = currentGroup || { room_type: s.room_type };
  const isOneTime = isOneTimeRoom(room);
  const roomTypeBadge = document.getElementById('overviewRoomTypeBadge');
  if (roomTypeBadge) {
    roomTypeBadge.textContent = getRoomTypeLabel(room);
    roomTypeBadge.className = isOneTime
      ? 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-gold-500/20 text-gold-300'
      : 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-navy-700 text-navy-200';
  }

  // A one-time receipt has no recurring spending dashboard. Hiding the outer
  // section removes its title, chart, categories and the vertical gap together.
  const spendingSection = document.getElementById('overviewSpendingSection');
  spendingSection?.classList.toggle('hidden', isOneTime);

  // Hero Card Spend & Budget
  const budget = s.budget || {};
  const totalSpent = (s.total_expenses !== undefined) ? s.total_expenses : (budget.total_spent !== undefined ? budget.total_spent : (budget.spent || 0));
  const targetBudget = budget.target_budget || 100000;
  const remaining = Math.max(0, targetBudget - totalSpent);
  const ratio = Math.min(100, Math.round((totalSpent / (targetBudget || 1)) * 100));

  const totalSpentEl = document.getElementById('overviewTotalSpent');
  if (totalSpentEl) totalSpentEl.textContent = formatCurrency(totalSpent);

  const budgetBar = document.getElementById('overviewBudgetBar');
  if (budgetBar) {
    budgetBar.style.width = `${ratio}%`;
    budgetBar.classList.toggle('is-warning', ratio > 80 && ratio <= 100);
    budgetBar.classList.toggle('is-over-budget', ratio > 100);
    budgetBar.setAttribute('aria-valuenow', String(ratio));
  }

  const remainingEl = document.getElementById('overviewRemaining');
  if (remainingEl) remainingEl.textContent = `Осталось ${formatCurrency(remaining)}`;

  const ratioEl = document.getElementById('overviewBudgetRatio');
  if (ratioEl) ratioEl.textContent = `${ratio}% из ${formatCurrency(targetBudget)}`;

  renderOverviewAiRecommendation(s, totalSpent, targetBudget, isOneTime);

  // The overview only shows debts belonging to the current user, never room-wide totals.
  const personalDebtText = document.getElementById('overviewPersonalDebtText');
  if (personalDebtText) {
    const debts = s.debts_summary || {};
    const iOwe = Number(debts.totalIOwe || 0);
    const owedToMe = Number(debts.totalOwedToMe || 0);
    if (iOwe > 0 && owedToMe > 0) {
      personalDebtText.innerHTML = `<span class="personal-debt-credit">Вам должны ${formatCurrency(owedToMe)}</span><span class="personal-debt-owed">Вы должны ${formatCurrency(iOwe)}</span>`;
    } else if (iOwe > 0) {
      personalDebtText.innerHTML = `<span class="personal-debt-owed">Вы должны ${formatCurrency(iOwe)}</span>`;
    } else if (owedToMe > 0) {
      personalDebtText.innerHTML = `<span class="personal-debt-credit">Вам должны ${formatCurrency(owedToMe)}</span>`;
    } else {
      personalDebtText.textContent = 'Личных долгов нет';
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

  // Do not leave a stale chart rendered behind when a user switches rooms.
  if (isOneTime) {
    if (donutChartInstance) {
      try { donutChartInstance.destroy(); } catch (e) {}
      donutChartInstance = null;
    }
  } else {
    renderOverviewDonut(s.categories || []);
  }

  // Recent Purchases List
  const recentBox = document.getElementById('overviewRecentList');
  if (recentBox) {
    const expenses = s.expenses || [];
    if (expenses.length === 0) {
      recentBox.innerHTML = `
        <div class="py-6 text-center text-xs text-slate-400">
          В этой комнате пока нет расходов.<br>Нажмите «+» чтобы добавить первый!
        </div>
      `;
    } else {
      recentBox.innerHTML = expenses.slice(0, 5).map(tx => {
        const color = getCategoryColor(tx.category);
        const icon = getMerchantIcon(tx.merchant || tx.title || tx.description, tx.category);
        return `
          <div class="overview-purchase-row flex items-center justify-between gap-3 cursor-pointer hover:bg-[#1C263B] transition-colors rounded-xl" onclick="openTransactionSheet(${tx.id})">
            <div class="flex items-center gap-3 min-w-0">
              <span class="overview-purchase-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-base shadow-sm" style="background-color: ${color}25; color: ${color}">
              ${icon}
              </span>
              <div class="min-w-0">
        <p class="truncate text-sm font-extrabold text-white">${getTransactionDisplayTitle(tx)}</p>
                <p class="text-xs text-slate-400 mt-0.5">${tx.payer_name || 'Участник'} · ${tx.created_at || 'Сегодня'}</p>
              </div>
            </div>
            <span class="font-black text-sm text-white shrink-0 ml-2">${formatCurrency(tx.amount)}</span>
          </div>
        `;
      }).join('');
    }
  }
}

async function fetchHistoryExpenses() {
  if (!state.groupId || state.historyLoading || Number(state.historyExpensesGroupId) === Number(state.groupId)) return;
  state.historyLoading = true;
  try {
    const url = appendTgUserId(`/api/rooms/${state.groupId}/expenses`);
    const res = await safeFetch(url, { headers: getRequestHeaders() }, 1, 12000);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.historyExpenses = Array.isArray(data.expenses) ? data.expenses : [];
    state.historyExpensesGroupId = state.groupId;
    if (state.currentTab === 'history') renderHistory();
  } catch (err) {
    // The overview data stays available as a graceful fallback.
    console.error('Failed to load complete expense history:', err);
  } finally {
    state.historyLoading = false;
  }
}

function openPersonalDebtOverview() {
  const debts = state.summary?.debts_summary || {};
  const iOwe = Number(debts.totalIOwe || 0);
  const owedToMe = Number(debts.totalOwedToMe || 0);
  state.debtFilter = iOwe > 0 ? 'i_owe' : owedToMe > 0 ? 'owed_to_me' : 'all';
  switchTab('family');
  const selectedTab = document.querySelector(`.debt-tab-btn[data-debt-filter="${state.debtFilter}"]`);
  selectedTab?.click();
}

function renderOverviewAiRecommendation(summary, totalSpent, targetBudget, isOneTime) {
  const section = document.getElementById('overviewAiRecommendationsSection');
  if (!section) return;

  section.classList.remove('hidden');
  const budget = summary?.budget || {};
  const roomId = Number(summary?.group_id || state.groupId || 0);
  const categories = mergeCategoryEntries(summary?.categories || [])
    .filter(category => Number(category.amount) > 0)
    .sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0));
  const tips = [];

  if (!totalSpent) {
    tips.push({ title: 'Первые советы появятся после покупки', text: isOneTime ? 'Добавьте позиции чека — SberWise покажет распределение суммы между участниками.' : 'Добавьте первый расход, и SberWise подскажет, какие категории стоит контролировать.' });
  } else {
    const percentUsed = Number(budget.percent_used ?? (totalSpent / Math.max(targetBudget, 1) * 100));
    const remaining = Math.max(0, targetBudget - totalSpent);
    const largestCategory = categories[0];
    const secondCategory = categories[1];

    if (largestCategory) {
      const categoryShare = Math.round(Number(largestCategory.amount) / totalSpent * 100);
      tips.push({ title: `Больше всего уходит на «${largestCategory.category}»`, text: `${categoryShare}% расходов (${formatCurrency(largestCategory.amount)}). Проверьте ближайшие покупки в этой категории — это главный резерв для экономии.` });
    }
    if (percentUsed >= 100) {
      tips.push({ title: 'Лимит комнаты уже превышен', text: `Расходы превысили бюджет на ${formatCurrency(totalSpent - targetBudget)}. Приостановите необязательные траты до конца периода.` });
    } else if (percentUsed >= 80) {
      tips.push({ title: 'Бюджет почти исчерпан', text: `Осталось ${formatCurrency(remaining)} — это ${Math.max(0, 100 - Math.round(percentUsed))}% лимита. Согласуйте крупные покупки с участниками.` });
    } else {
      tips.push({ title: 'Бюджет комнаты в норме', text: `Использовано ${Math.round(percentUsed)}% из ${formatCurrency(targetBudget)}. Остаток ${formatCurrency(remaining)} можно оставить на запланированные покупки.` });
    }
    if (secondCategory) {
      const firstTwoShare = Math.round((Number(largestCategory.amount) + Number(secondCategory.amount)) / totalSpent * 100);
      tips.push({ title: 'Расходы сосредоточены в двух категориях', text: `«${largestCategory.category}» и «${secondCategory.category}» составляют ${firstTwoShare}% расходов комнаты. Сравните покупки в этих категориях перед следующими тратами.` });
    } else {
      const expenseCount = (summary?.expenses || []).length;
      tips.push({ title: 'Добавляйте расходы сразу после покупки', text: `Сейчас учтено ${expenseCount} ${pluralize(expenseCount, 'покупка', 'покупки', 'покупок')}. Чем полнее история, тем точнее подсказки по этой комнате.` });
    }
  }

  if (state.overviewAiRecommendationRoomId !== roomId) {
    state.overviewAiRecommendationRoomId = roomId;
    state.overviewAiRecommendationIndex = 0;
  }
  state.overviewAiRecommendations = tips;
  if (state.overviewAiRecommendationIndex >= tips.length) state.overviewAiRecommendationIndex = 0;
  updateOverviewAiRecommendationCard();
}

function updateOverviewAiRecommendationCard() {
  const tips = state.overviewAiRecommendations || [];
  const title = document.getElementById('overviewAiRecommendationTitle');
  const text = document.getElementById('overviewAiRecommendationText');
  const position = document.getElementById('overviewAiRecommendationPosition');
  const previous = document.getElementById('btnOverviewAiPrevious');
  const next = document.getElementById('btnOverviewAiNext');
  if (!title || !text || !position || !previous || !next || !tips.length) return;
  const index = Math.max(0, Math.min(Number(state.overviewAiRecommendationIndex || 0), tips.length - 1));
  const tip = tips[index];
  state.overviewAiRecommendationIndex = index;
  title.textContent = tip.title;
  text.textContent = tip.text;
  position.textContent = `${index + 1} из ${tips.length}`;
  previous.disabled = tips.length < 2;
  next.disabled = tips.length < 2;
}

function changeOverviewAiRecommendation(direction) {
  const tips = state.overviewAiRecommendations || [];
  if (tips.length < 2) return;
  const current = Number(state.overviewAiRecommendationIndex || 0);
  state.overviewAiRecommendationIndex = (current + direction + tips.length) % tips.length;
  updateOverviewAiRecommendationCard();
}

function renderOverviewDonut(categories) {
  const canvas = document.getElementById('overviewDonutChart');
  const centerTotal = document.getElementById('donutCenterTotal');
  const topCategoriesBox = document.getElementById('overviewTopCategories');
  if (!canvas) return;

  // The room card intentionally shares Analytics' normalization, grouping,
  // palette and gradients. It only changes the physical chart size.
  const chartCategories = prepareAnalyticsDonutCategories(categories);
  const total = chartCategories.reduce((sum, c) => sum + (Number(c.amount) || 0), 0);
  const decorated = chartCategories.map((item, index) => ({
    ...item,
    color: ANALYTICS_DONUT_PALETTE[index % ANALYTICS_DONUT_PALETTE.length],
    percent: total ? Math.round((item.amount / total) * 1000) / 10 : 0,
  }));
  state.selectedRoomDonutCategory = null;
  renderRoomDonutDetail(null);
  if (centerTotal) centerTotal.textContent = formatCurrency(total);

  if (topCategoriesBox) {
    topCategoriesBox.innerHTML = decorated.length === 0
      ? '<p class="overview-donut-empty">Пока нет расходов</p>'
      : decorated.slice(0, 3).map(c => {
      const pct = Math.round(c.percent);
      return `
        <div class="overview-top-category">
          <div class="overview-top-category-head">
            <span class="overview-top-category-icon" style="color:${c.color}">${getCategoryIcon(c.category)}</span>
            <span class="overview-top-category-name">${escapeHtml(getCategoryLabel(c.category))}</span>
            <span class="overview-top-category-percent">${pct}%</span>
          </div>
          <div class="overview-top-category-track">
            <div class="overview-top-category-fill" style="width: ${pct}%; background-color: ${c.color}"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  if (donutChartInstance) donutChartInstance.destroy();
  if (!window.Chart) return;
  donutChartInstance = createExpenseDonutChart({
    canvas,
    categories: decorated,
    isEmpty: decorated.length === 0,
    compact: true,
    tooltipStageSelector: '.overview-donut-stage',
    onSegmentTap: item => {
      if (!item || state.selectedRoomDonutCategory === item.category) {
        state.selectedRoomDonutCategory = null;
        renderRoomDonutDetail(null);
        return;
      }
      state.selectedRoomDonutCategory = item.category;
      renderRoomDonutDetail(item);
    },
  });
  refreshIcons();
}

// 2. History Screen
function renderHistory() {
  const s = state.summary;
  if (!s) return;
  const allTx = Number(state.historyExpensesGroupId) === Number(state.groupId)
    ? (state.historyExpenses || [])
    : (s.expenses || []);

  let filtered = allTx.filter(tx => {
    if (!matchesHistoryCategory(tx.category, state.historyCategory)) return false;
    if (state.historyDate && String(tx.created_at || '').slice(0, 10) !== state.historyDate) return false;
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
  const dateButton = document.getElementById('btnHistoryDate');
  if (dateButton) dateButton.classList.toggle('is-active', Boolean(state.historyDate));

  const container = document.getElementById('historyListContainer');
  if (!container) return;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="history-empty-state">
        <span class="history-empty-icon" aria-hidden="true">⌕</span>
        <p class="history-empty-title">Ничего не найдено</p>
        <p class="history-empty-description">Попробуйте изменить категорию или поисковый запрос</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="history-list-card">
      ${filtered.map(tx => {
        const color = getCategoryColor(tx.category);
        const icon = getMerchantIcon(tx.merchant || tx.title || tx.description, tx.category);
        const displayTitle = getTransactionDisplayTitle(tx);
        return `
          <div class="history-row" onclick="openTransactionSheet(${tx.id})">
            <div class="history-row-main">
              <span class="history-row-icon" style="--history-accent: ${color}; --history-accent-soft: ${color}2b">
                ${icon}
              </span>
              <div class="history-row-copy">
                <p class="history-row-title">${displayTitle}</p>
                <p class="history-row-meta">${tx.payer_name || 'Участник'} · ${tx.created_at || 'Сегодня'}</p>
              </div>
            </div>
            <span class="history-row-amount">${formatCurrency(tx.amount)}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

// 3. Analytics Screen
async function fetchAnalytics() {
  if (!state.groupId || state.analyticsLoading) return;
  state.analyticsLoading = true;

  try {
    let url = `/api/group/${state.groupId}/analytics?period=${state.analyticsPeriod.type || 'current_month'}`;
    if (state.analyticsPeriod.type === 'custom') {
      if (state.analyticsPeriod.from) url += `&from=${encodeURIComponent(state.analyticsPeriod.from)}`;
      if (state.analyticsPeriod.to) url += `&to=${encodeURIComponent(state.analyticsPeriod.to)}`;
    }
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `&tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    state.analyticsData = data;
    renderAnalytics();
  } catch (err) {
    if (lifecycle.suspended) return;
    console.error('Failed to fetch room analytics:', err);
    renderAnalytics();
  } finally {
    state.analyticsLoading = false;
  }
}

function renderAnalytics() {
  const data = state.analyticsData;
  if (!data) {
    if (!state.analyticsLoading && state.groupId) {
      fetchAnalytics();
    }
    return;
  }

  const currency = data.currency || 'RUB';

  // Subtitle & Button label
  const subEl = document.getElementById('analyticsSubtitle');
  if (subEl) subEl.textContent = data.period?.label || 'Текущий период';

  const btnLabelEl = document.getElementById('analyticsPeriodButtonLabel');
  if (btnLabelEl) btnLabelEl.textContent = data.period?.button_label || 'Период';

  // Average check
  const avgEl = document.getElementById('analyticsAvgCheck');
  if (avgEl) avgEl.textContent = formatCurrency(data.average || 0, currency);

  const avgNoteEl = document.getElementById('analyticsAvgNote');
  if (avgNoteEl) {
    avgNoteEl.textContent = data.count > 0 ? 'оптимально' : 'нет трат';
  }

  // Count
  const countEl = document.getElementById('analyticsTxCount');
  if (countEl) countEl.textContent = data.count || 0;

  // Total badge
  const badgeEl = document.getElementById('analyticsTotalBadge');
  if (badgeEl) badgeEl.textContent = formatCurrency(data.total || 0, currency);

  // Timeline section title & subtitle
  const timeTitleEl = document.getElementById('analyticsTimelineTitle');
  if (timeTitleEl) timeTitleEl.textContent = data.timeline_meta?.title || 'Динамика по неделям';

  const timeSubEl = document.getElementById('analyticsTimelineSubtitle');
  if (timeSubEl) timeSubEl.textContent = data.timeline_meta?.subtitle || 'Распределение расходов';

  renderAnalyticsDonut(data.categories || [], currency);

  // Chart rendering with real timeline and room currency
  renderWeeklyChart(data.timeline || [], currency);
  updatePeriodModalCheckmarks();
  refreshIcons();
}

function prepareAnalyticsDonutCategories(categories = []) {
  const merged = mergeCategoryEntries(categories)
    .map(item => ({ ...item, amount: Math.max(0, Number(item.amount) || 0) }))
    .filter(item => item.amount > 0)
    .sort((a, b) => b.amount - a.amount);
  if (merged.length <= 5) return merged;

  // Presentation-only grouping prevents a crowded ring; source analytics totals stay unchanged.
  const visible = merged.slice(0, 4);
  const remainder = merged.slice(4).reduce((sum, item) => sum + item.amount, 0);
  const existingOther = visible.find(item => canonicalCategoryName(item.category) === 'Другое');
  if (existingOther) existingOther.amount += remainder;
  else visible.push({ category: 'Другое', amount: remainder });
  return visible;
}

function renderAnalyticsDonut(categories, currency = 'RUB') {
  const canvas = document.getElementById('analyticsDonutChart');
  const totalEl = document.getElementById('analyticsDonutTotal');
  const emptyEl = document.getElementById('analyticsDonutEmptyText');
  const list = document.getElementById('analyticsCategoriesList');
  const segmentIcons = document.getElementById('analyticsDonutSegmentIcons');
  if (!canvas || !list) return;

  const chartCategories = prepareAnalyticsDonutCategories(categories);
  const total = chartCategories.reduce((sum, item) => sum + item.amount, 0);
  const decorated = chartCategories.map((item, index) => ({
    ...item,
    color: ANALYTICS_DONUT_PALETTE[index % ANALYTICS_DONUT_PALETTE.length],
    percent: total ? Math.round((item.amount / total) * 1000) / 10 : 0,
  }));
  if (totalEl) totalEl.textContent = formatCurrency(total, currency);
  emptyEl?.classList.toggle('hidden', total > 0);

  if (segmentIcons) segmentIcons.innerHTML = '';

  if (analyticsDonutChartInstance) {
    try { analyticsDonutChartInstance.destroy(); } catch (e) {}
    analyticsDonutChartInstance = null;
  }

  if (!window.Chart) return;
  const isEmpty = decorated.length === 0;
  analyticsDonutChartInstance = createExpenseDonutChart({ canvas, categories: decorated, currency, isEmpty, compact: false, tooltipStageSelector: '.analytics-donut-stage' });
  const currentChart = analyticsDonutChartInstance;
  renderAnalyticsDonutSegmentLabels(currentChart, decorated);
  requestAnimationFrame(() => {
    if (analyticsDonutChartInstance === currentChart) {
      renderAnalyticsDonutSegmentLabels(currentChart, decorated);
      // Labels are injected after the general page icon refresh. Convert this
      // second, geometry-corrected pass as well, otherwise raw <i> tags stay invisible.
      refreshIcons();
    }
  });

  list.innerHTML = isEmpty
    ? '<p class="analytics-empty-state">За выбранный период расходов нет</p>'
    : decorated.map(item => `
      <div class="analytics-category-row">
        <div class="analytics-category-main">
          <span class="analytics-category-marker" style="color:${item.color}; background:${item.color}"></span>
          <span class="analytics-category-icon" style="color:${item.color}">${getCategoryIcon(item.category)}</span>
          <div class="analytics-category-copy">
            <div class="analytics-category-top">
              <span class="analytics-category-name">${escapeHtml(getCategoryLabel(item.category))}</span>
              <span class="analytics-category-percent">${item.percent}%</span>
              <span class="analytics-category-amount">${formatCurrency(item.amount, currency)}</span>
            </div>
          </div>
        </div>
      </div>
    `).join('');
}

function renderAnalyticsDonutSegmentLabels(chart, categories) {
  const host = document.getElementById('analyticsDonutSegmentIcons');
  if (!host || !chart || !categories.length || !chart.width || !chart.height) return;
  const arcs = chart.getDatasetMeta(0)?.data || [];
  const placed = [];
  const labels = [];

  const intersects = (a, b) => !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
  arcs.forEach((arc, index) => {
    const item = categories[index];
    if (!item) return;
    const { x, y, startAngle, endAngle, innerRadius, outerRadius } = arc.getProps(
      ['x', 'y', 'startAngle', 'endAngle', 'innerRadius', 'outerRadius'], true
    );
    const angularSpan = Math.abs(endAngle - startAngle);
    const percent = Number(item.percent) || 0;
    if (percent < 4 || angularSpan < 0.25) return; // truly tiny: legend only

    const large = percent >= 12 && angularSpan >= 0.75;
    const radius = innerRadius + (outerRadius - innerRadius) * (large ? 0.55 : 0.52);
    const midAngle = (startAngle + endAngle) / 2;
    const labelX = x + Math.cos(midAngle) * radius;
    const labelY = y + Math.sin(midAngle) * radius;
    // 8–10% arcs still have room for a compact icon plus its percentage.
    const width = large ? 38 : 30;
    const height = large ? 42 : 32;
    const box = { left: labelX - width / 2, right: labelX + width / 2, top: labelY - height / 2, bottom: labelY + height / 2 };
    if (placed.some(existing => intersects(box, existing))) return; // small label yields to an already placed one
    placed.push(box);

    const left = (labelX / chart.width) * 100;
    const top = (labelY / chart.height) * 100;
    const label = `${Math.round(percent)}%`;
    labels.push(`<span class="analytics-donut-segment-icon ${large ? 'is-full' : 'is-compact'}" style="left:${left}%;top:${top}%" title="${escapeHtml(getCategoryLabel(item.category))}">${getCategoryIcon(item.category, 'analytics-donut-segment-svg')}<b>${label}</b></span>`);
  });
  host.innerHTML = labels.join('');
}

function showAppConfirm(title, message, confirmLabel = 'Подтвердить', destructive = false) {
  return new Promise(resolve => {
    const titleEl = document.getElementById('actionConfirmTitle');
    const textEl = document.getElementById('actionConfirmText');
    const accept = document.getElementById('btnAcceptActionConfirm');
    const cancel = document.getElementById('btnCancelActionConfirm');
    if (!titleEl || !textEl || !accept || !cancel) return resolve(false);
    titleEl.textContent = title;
    textEl.textContent = message;
    accept.textContent = confirmLabel;
    accept.className = destructive
      ? 'rounded-xl bg-rose-500 px-3 py-3 text-sm font-black text-white active:scale-95'
      : 'rounded-xl bg-[#00D29D] px-3 py-3 text-sm font-black text-[#06281E] active:scale-95';
    const done = value => {
      accept.onclick = null;
      cancel.onclick = null;
      closeSheets();
      resolve(value);
    };
    accept.onclick = () => done(true);
    cancel.onclick = () => done(false);
    openSheet('sheet-action-confirm');
  });
}

function detectInviteToken() {
  const params = new URLSearchParams(window.location.search);
  const direct = params.get('invite');
  if (direct) return direct;
  const startParam = tg?.initDataUnsafe?.start_param;
  return startParam && String(startParam).startsWith('invite_') ? String(startParam).slice(7) : null;
}

function restoreAppAfterInvite() {
  document.getElementById('welcomeScreen')?.remove();
  const mainContent = document.getElementById('mainContent');
  const bottomNav = document.getElementById('bottomNav');
  mainContent?.classList.remove('hidden');
  bottomNav?.classList.remove('hidden');
  mainContent?.removeAttribute('hidden');
  bottomNav?.removeAttribute('hidden');
  if (mainContent) mainContent.style.display = '';
  if (bottomNav) bottomNav.style.display = '';
}

async function showInviteAcceptanceScreen(token) {
  const res = await fetch(appendTgUserId(`/api/invites/${encodeURIComponent(token)}`), { headers: getRequestHeaders() });
  const data = await res.json().catch(() => ({}));
  const mainContent = document.getElementById('mainContent');
  const bottomNav = document.getElementById('bottomNav');
  mainContent?.classList.add('hidden'); bottomNav?.classList.add('hidden');
  const screen = document.createElement('main');
  screen.id = 'inviteAcceptanceScreen';
  state.inviteScreenOpen = true;
  screen.className = 'fixed inset-0 z-[96] flex items-end bg-[#07131D] p-3';
  if (!res.ok || !data.valid) {
    screen.innerHTML = `<section class="w-full rounded-[28px] border border-rose-400/30 bg-[#0E1B29] p-6 text-center"><i data-lucide="circle-x" class="mx-auto h-10 w-10 text-rose-400"></i><h1 class="mt-4 text-xl font-black text-white">Приглашение недействительно</h1><p class="mt-2 text-sm text-slate-400">${escapeHtml(data.error || 'Ссылка истекла или больше не работает.')}</p></section>`;
    document.body.appendChild(screen); refreshIcons(); return;
  }
  const invite = data.invite;
  const alreadyMember = Boolean(data.already_member);
  screen.innerHTML = `<section class="w-full rounded-[28px] border border-mint-500/30 bg-[#0E1B29] p-6 pb-[max(24px,env(safe-area-inset-bottom))] text-center"><div class="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-mint-500/15 text-mint-400"><i data-lucide="users-round" class="h-7 w-7"></i></div><p class="mt-4 text-xs font-black uppercase tracking-[.16em] text-mint-400">${alreadyMember ? 'Вы уже состоите в комнате' : 'Вас пригласили в комнату'}</p><h1 class="mt-2 text-2xl font-black text-white">${escapeHtml(invite.room_name)}</h1><p class="mt-3 text-sm text-slate-400">Создатель: ${escapeHtml(invite.creator_name)} · ${Number(invite.members_count)} участников</p><button id="inviteJoinButton" class="mt-6 h-12 w-full rounded-2xl bg-[#00D29D] text-sm font-black text-[#06281E]">${alreadyMember ? 'Перейти в комнату' : 'Присоединиться'}</button><button id="inviteCancelButton" class="mt-2 h-11 w-full text-sm font-bold text-slate-400">Отмена</button></section>`;
  document.body.appendChild(screen);
  screen.querySelector('#inviteCancelButton').addEventListener('click', () => {
    screen.remove(); state.inviteScreenOpen = false; ensureWelcomeScreen();
  });
  screen.querySelector('#inviteJoinButton').addEventListener('click', async (event) => {
    if (alreadyMember) { state.groupId = invite.room_id; screen.remove(); state.inviteScreenOpen = false; restoreAppAfterInvite(); await fetchSummary(); return; }
    const button = event.currentTarget; button.disabled = true; button.textContent = 'Присоединяем…';
    const joinRes = await fetch(appendTgUserId(`/api/invites/${encodeURIComponent(token)}/join`), { method: 'POST', headers: getRequestHeaders() });
    const join = await joinRes.json().catch(() => ({}));
    if (!joinRes.ok) { button.disabled = false; button.textContent = 'Присоединиться'; return showToast(join.error || 'Не удалось присоединиться', 'error'); }
    state.groupId = join.room_id; screen.remove(); state.inviteScreenOpen = false; restoreAppAfterInvite(); await fetchSummary(); showToast(join.already_member ? 'Вы уже состоите в этой комнате' : 'Вы присоединились к комнате', 'success');
  });
  refreshIcons();
}

function setNotificationBadge(unreadCount, totalCount = 0) {
  const unread = Math.max(0, Number(unreadCount) || 0);
  const total = Math.max(0, Number(totalCount) || 0);
  const visibleCount = unread || total;
  const bellBadge = document.getElementById('bellDot');
  const pickerBadge = document.getElementById('addExpenseBellBadge');
  if (bellBadge) {
    bellBadge.textContent = visibleCount > 99 ? '99+' : String(visibleCount);
    bellBadge.classList.toggle('hidden', visibleCount === 0);
    bellBadge.classList.toggle('has-unread', unread > 0);
  }
  const bell = document.getElementById('btnBell');
  if (bell) {
    bell.classList.toggle('has-notifications', visibleCount > 0);
    bell.classList.toggle('has-unread', unread > 0);
    bell.setAttribute('aria-label', unread ? `Уведомления: ${unread} непрочитанных` : (total ? `Уведомления: ${total}` : 'Уведомления'));
  }
  if (pickerBadge) pickerBadge.classList.toggle('hidden', unread === 0);
}

async function refreshNotificationBadge() {
  if (!state.groupId) return;
  try {
    const res = await safeFetch(appendTgUserId(`/api/group/${state.groupId}/notifications`), { headers: getRequestHeaders() }, 1, 10000);
    if (!res.ok) return;
    const data = await res.json();
    setNotificationBadge(data.unread_count, data.count);
  } catch (err) {
    console.warn('Failed to refresh notification badge:', err);
  }
}

function renderWeeklyChart(timeline, currency = 'RUB') {
  const canvas = document.getElementById('analyticsWeeklyChart');
  if (!canvas) return;

  if (weeklyChartInstance) {
    try {
      weeklyChartInstance.destroy();
    } catch (e) {}
    weeklyChartInstance = null;
  }

  const labels = (timeline || []).map(t => t.label);
  const dataValues = (timeline || []).map(t => t.amount || 0);
  const fullLabels = (timeline || []).map(t => t.full_label || t.label);

  const ctx = canvas.getContext('2d');
  weeklyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Расходы',
        data: dataValues,
        backgroundColor: '#00D29D',
        hoverBackgroundColor: '#00E599',
        borderRadius: 8,
        borderSkipped: false,
        maxBarThickness: 40
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: '#94A3B8',
            font: { size: 10, weight: '600' }
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: '#64748B',
            font: { size: 10 },
            callback: (v) => v >= 1000 ? `${Math.round(v / 1000)}k` : `${v}`
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#151D2E',
          titleColor: '#FFFFFF',
          bodyColor: '#00E599',
          borderColor: '#222E46',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 12,
          callbacks: {
            title: function(context) {
              const idx = context[0].dataIndex;
              return fullLabels[idx] || labels[idx] || '';
            },
            label: function(context) {
              const val = context.raw || 0;
              return `Расходы: ${formatCurrency(val, currency)}`;
            }
          }
        }
      }
    }
  });
}

function updatePeriodModalCheckmarks() {
  const currentType = state.analyticsPeriod?.type || 'current_month';
  document.querySelectorAll('.analytics-period-opt').forEach(btn => {
    const pType = btn.getAttribute('data-period-type');
    const checkIcon = btn.querySelector('.period-check-icon i');
    const container = btn.querySelector('.period-check-icon');
    if (checkIcon && container) {
      if (pType === currentType) {
        checkIcon.classList.remove('hidden');
        container.classList.add('border-[#00D29D]', 'bg-[#00D29D]/10');
      } else {
        checkIcon.classList.add('hidden');
        container.classList.remove('border-[#00D29D]', 'bg-[#00D29D]/10');
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
    const debts = s.simplified_debts || s.debts || [];
    if (debts.length === 0) {
      debtsList.innerHTML = `
        <div class="rounded-2xl bg-emerald-950/40 p-5 text-center text-emerald-300 border border-emerald-800/40">
          <i data-lucide="check-circle-2" class="mx-auto w-6 h-6 mb-1 text-[#00E599]"></i>
          <p class="font-bold text-sm text-white">Все в расчёте!</p>
          <p class="text-xs text-slate-400 mt-0.5">В комнате нет непогашенных переводов</p>
        </div>
      `;
      if (debtsStatus) debtsStatus.textContent = 'Все рассчитались';
    } else {
      if (debtsStatus) debtsStatus.textContent = `${debts.length} перевода к расчёту`;
      debtsList.innerHTML = debts.map(d => {
        return `
          <div class="flex items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] shadow-card border border-[#222E46]">
            <div class="flex items-center gap-3">
              <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800 text-cyan-400 font-extrabold text-xs border border-slate-700">
                ${(d.from_name || 'U')[0]}
              </span>
              <div>
                <p class="text-xs font-bold text-white">${d.from_name} → ${d.to_name}</p>
                <p class="text-[10px] text-slate-400">банковский перевод</p>
              </div>
            </div>
            <button type="button" class="btn-settle-action px-3 py-1.5 rounded-xl bg-[#00D29D]/20 text-[#00E599] border border-[#00D29D]/30 font-extrabold text-xs hover:bg-[#00D29D]/30 transition-colors" onclick="openSettlementSheet({from_name: '${d.from_name}', to_name: '${d.to_name}', amount: ${d.amount}})">
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
      const balColor = bal > 0 ? 'text-[#00E599]' : bal < 0 ? 'text-rose-400' : 'text-slate-400';
      const fico = 720 + ((idx * 37) % 120);

      return `
        <div class="flex items-center justify-between py-3">
          <div class="flex items-center gap-3">
            <span class="inline-flex h-9 w-9 items-center justify-center rounded-full text-xs font-extrabold text-white" style="background-color: ${AVATAR_COLORS[idx % AVATAR_COLORS.length]}">
              ${(m.name || 'U')[0]}
            </span>
            <div>
              <p class="text-xs font-extrabold text-white">${m.name}</p>
              <div class="flex items-center gap-1.5 mt-0.5">
                <span class="rounded bg-cyan-950/60 border border-cyan-800/40 px-1.5 py-0.5 text-[10px] font-bold text-cyan-300">${fico}</span>
                <span class="text-[10px] text-slate-400">СберРейтинг</span>
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
  let data;
  try {
    data = await fetchGroupDebts(state.groupId, state.debtFilter);
  } catch (err) {
    const container = document.getElementById('debtsListContainer');
    if (container) container.innerHTML = '<div class="rounded-2xl bg-[#151D2E] p-5 text-center border border-rose-800/40"><p class="text-xs font-bold text-rose-300">Не удалось загрузить долги</p><p class="text-[11px] text-slate-400 mt-1">Проверьте соединение и попробуйте ещё раз.</p></div>';
    return;
  }

  state.debtsList = data.debts || [];
  state.debtsSummary = data.summary || {};
  updateResultsSettlementStatus(data.summary || {}, state.debtsList);

  const owedToMeEl = document.getElementById('debtsOwedToMeTotal');
  if (owedToMeEl) owedToMeEl.textContent = formatCurrency(data.summary?.totalOwedToMe ?? data.summary?.total_owed_to_me ?? 0);

  const iOweEl = document.getElementById('debtsIOweTotal');
  if (iOweEl) iOweEl.textContent = formatCurrency(data.summary?.totalIOwe ?? data.summary?.total_i_owe ?? 0);

  const badgeEl = document.getElementById('debtsCountBadge');
  if (badgeEl) {
    const count = state.debtsList.filter(d => d.status === 'active' || d.status === 'partially_paid').length;
    badgeEl.textContent = `${count} активных`;
  }

  const container = document.getElementById('debtsListContainer');
  if (!container) return;

  const currentUserId = state.currentUser?.id;
  // Closed debts are kept in their payment history, not in the actionable register.
  const debts = state.debtsList.filter(d =>
    (d.status === 'active' || d.status === 'partially_paid') && Number(d.remaining_amount) > 0
  );

  if (debts.length === 0) {
    container.innerHTML = `
      <div class="rounded-2xl bg-[#151D2E] p-6 text-center border border-[#222E46] shadow-card">
        <div class="w-10 h-10 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto mb-2 border border-slate-700">
          <i data-lucide="receipt-text" class="w-5 h-5"></i>
        </div>
        <p class="text-xs font-bold text-white">Нет активных долгов</p>
        <p class="text-[11px] text-slate-400 mt-0.5">Все долги в этой категории погашены</p>
      </div>
    `;
    refreshIcons();
    return;
  }

  container.innerHTML = debts.map(d => {
    const isOverdue = Boolean(d.is_overdue);
    const isIOwe = currentUserId && Number(d.debtor_user_id) === Number(currentUserId);
    const isOwedToMe = currentUserId && Number(d.creditor_user_id) === Number(currentUserId);
    const canPay = (d.can_pay ?? isIOwe) && Number(d.remaining_amount) > 0 && (d.status === 'active' || d.status === 'partially_paid');

    let roleBadge = '';
    let dirIcon = '';
    let dirColor = '';
    if (isIOwe) {
      roleBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-950/60 text-rose-300 border border-rose-800/40">Я должен</span>';
      dirIcon = 'arrow-up-right';
      dirColor = 'text-rose-400 bg-rose-950/60 border border-rose-800/40';
    } else if (isOwedToMe) {
      roleBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">Мне должны</span>';
      dirIcon = 'arrow-down-left';
      dirColor = 'text-[#00E599] bg-emerald-950/60 border border-emerald-800/40';
    } else {
      roleBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">${d.debtor_name} → ${d.creditor_name}</span>`;
      dirIcon = 'arrow-right-left';
      dirColor = 'text-slate-300 bg-slate-800 border border-slate-700';
    }

    let statusBadge = '';
    if (isOverdue) {
      statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500 text-white animate-pulse">🔴 Просрочен</span>`;
    } else if (d.status === 'active') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-950/60 text-cyan-300 border border-cyan-800/40">Активен</span>';
    } else if (d.status === 'partially_paid') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-800/40">Частично</span>';
    } else if (d.status === 'paid') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">Погашен</span>';
    } else if (d.status === 'cancelled') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">Отменён</span>';
    }

    const linkedExpense = (state.summary?.expenses || []).find(exp => Number(exp.id) === Number(d.expense_id));
    const rawDebtTitle = String(linkedExpense?.description || d.description || '').replace(/\s+из\s+WebApp\s*$/i, '').trim();
    const debtTitle = rawDebtTitle || getCategoryLabel(linkedExpense?.category || d.category, 'Расход');
    return `
      <div class="debt-card rounded-2xl bg-[#151D2E] p-3.5 shadow-card border ${isOverdue ? 'border-rose-500 ring-1 ring-rose-500/40' : 'border-[#222E46]'} cursor-pointer hover:border-cyan-500/40 transition-all active:scale-[0.99]" onclick="openDebtDetailSheet(${d.id})">
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
               <h3 class="text-xs font-extrabold text-white mt-1 leading-snug">${escapeHtml(debtTitle)}</h3>
            </div>
          </div>
          <div class="text-right shrink-0">
            <p class="text-sm font-black text-white">${formatCurrency(d.remaining_amount)}</p>
            ${d.remaining_amount < d.original_amount ? `<p class="text-[10px] text-slate-400">из ${formatCurrency(d.original_amount)}</p>` : ''}
            ${canPay ? `<button type="button" class="mt-2 rounded-lg border border-[#00D29D]/40 bg-[#00D29D]/15 px-2.5 py-1 text-[11px] font-black text-[#00E599] transition-colors hover:bg-[#00D29D]/25" onclick="event.stopPropagation(); openDebtPaymentFor(${Number(d.id)})">Оплатить</button>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
  refreshIcons();
}

function updateResultsSettlementStatus(summary, visibleDebts) {
  const debtsStatus = document.getElementById('familyDebtsStatus');
  const debtsList = document.getElementById('familyDebtsList');
  if (!debtsStatus || !debtsList) return;

  const activeManualCount = Number(summary.activeDebtsIOweCount || 0);
  const transfers = state.summary?.simplified_debts || state.summary?.debts || [];
  document.getElementById('familyManualDebtNotice')?.remove();

  if (activeManualCount <= 0) {
    if (!transfers.length) {
      debtsStatus.textContent = 'Все рассчитались';
      debtsList.innerHTML = '<div class="rounded-2xl bg-emerald-950/40 p-5 text-center text-emerald-300 border border-emerald-800/40"><i data-lucide="check-circle-2" class="mx-auto w-6 h-6 mb-1 text-[#00E599]"></i><p class="font-bold text-sm text-white">Все в расчёте!</p><p class="text-xs text-slate-400 mt-0.5">В комнате нет непогашенных переводов</p></div>';
    } else {
      debtsStatus.textContent = `${transfers.length} перевода к расчёту`;
    }
    refreshIcons();
    return;
  }

  const debtWord = activeManualCount === 1 ? 'долг' : (activeManualCount < 5 ? 'долга' : 'долгов');
  const manualTotal = Number(summary.totalIOwe || 0);
  const manualNote = `Вы должны ${formatCurrency(manualTotal)} · ${activeManualCount} ${debtWord}`;

  if (!transfers.length) {
    debtsStatus.textContent = 'Ваши долги';
    debtsList.innerHTML = `
      <div class="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 text-center">
        <i data-lucide="circle-dollar-sign" class="mx-auto mb-1 h-6 w-6 text-amber-300"></i>
        <p class="text-sm font-bold text-white">${manualNote}</p>
        <p class="mt-0.5 text-xs text-slate-400">Только ваши обязательства перед другими участниками.</p>
      </div>
    `;
  } else {
    debtsStatus.textContent = `${transfers.length} перевода · ваши долги`;
    debtsList.insertAdjacentHTML('beforeend', `
      <div id="familyManualDebtNotice" class="mt-2 rounded-xl border border-amber-500/25 bg-amber-950/15 px-3 py-2 text-xs text-amber-100">
        ${manualNote}
      </div>
    `);
  }
  refreshIcons();
}

async function openNotificationsCenter() {
  const list = document.getElementById('notificationsList');
  state.notificationsOpen = true;
  openSheet('sheet-notifications');
  if (!state.groupId || !list) return;
  try {
    const res = await fetch(appendTgUserId(`/api/group/${state.groupId}/notifications`), { headers: getRequestHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    const notifications = data.notifications || [];
    setNotificationBadge(data.unread_count, data.count);
    if (!notifications.length) {
      list.innerHTML = '<div class="py-8 text-center text-sm font-bold text-slate-300">Новых уведомлений нет</div>';
      return;
    }
    list.innerHTML = notifications.map(n => {
      const icon = n.type === 'budget_warning' ? 'alert-triangle' : (n.type === 'debt_paid' ? 'check-circle-2' : 'bell-ring');
      const notificationMerchant = n.merchant || n.expense_merchant || n.title || n.body || n.text;
      const merchantIcon = getMerchantIcon(notificationMerchant, n.category);
      const notificationIcon = getMerchantLogo(notificationMerchant)
        ? merchantIcon
        : `<i data-lucide="${icon}" class="w-4 h-4"></i>`;
      const entityId = n.entity_id || n.debt_id;
      const action = entityId ? ` onclick="openNotificationDebt(${Number(entityId)}); markNotificationRead(${Number(n.id)})"` : ` onclick="markNotificationRead(${Number(n.id)})"`;
      const unreadClass = n.read_at ? 'opacity-70' : 'ring-1 ring-[#00D29D]/30';
      return `<button type="button" class="w-full text-left rounded-2xl bg-[#151D2E] border border-[#222E46] p-3.5 hover:border-[#00D29D]/50 ${unreadClass}"${action}>
        <div class="flex gap-3"><span class="notification-row-icon flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#10242B] text-[#00E599]">${notificationIcon}</span>
        <div><p class="text-xs font-extrabold text-white">${escapeHtml(n.title || 'Уведомление')}</p><p class="text-[11px] text-slate-400 mt-1">${escapeHtml(n.body || n.text || '')}</p></div></div>
      </button>`;
    }).join('');
    refreshIcons();
  } catch (err) {
    console.error('Failed to load notifications:', err);
    list.innerHTML = '<div class="py-8 text-center text-sm font-bold text-rose-300">Не удалось загрузить уведомления</div>';
  }
}

function toggleNotifications() {
  if (state.notificationsOpen) {
    closeNotifications();
    return;
  }
  openNotificationsCenter();
}

function closeNotifications() {
  const notification = document.getElementById('sheet-notifications');
  if (!notification) return;
  state.notificationsOpen = false;
  notification.classList.remove('active');
  notification.classList.add('hidden');

  // Keep the underlying picker and shared overlay mounted when present.
  const underlyingSheet = document.querySelector('.sheet-content.active');
  state.activeSheet = underlyingSheet?.id || null;
  if (!underlyingSheet) {
    const overlay = document.getElementById('sheetOverlay');
    overlay?.classList.remove('active');
    overlay?.classList.add('hidden');
  }
}

async function markNotificationRead(id) {
  if (!state.groupId || !id) return;
  try { await fetch(appendTgUserId(`/api/group/${state.groupId}/notifications/${id}/read`), { method: 'POST', headers: getRequestHeaders() }); await refreshNotificationBadge(); } catch (e) { console.warn(e); }
}

async function markAllNotificationsRead() {
  if (!state.groupId) return;
  try { await fetch(appendTgUserId(`/api/group/${state.groupId}/notifications/read-all`), { method: 'POST', headers: getRequestHeaders() }); await refreshNotificationBadge(); await openNotificationsCenter(); } catch (e) { console.warn(e); }
}

function openNotificationDebt(debtId) {
  closeSheets();
  setTimeout(() => openDebtDetailSheet(Number(debtId)), 240);
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
  document.getElementById('roomDeleteSection')?.classList.toggle('hidden', !s.can_delete_room);
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
        <div class="w-12 h-12 rounded-2xl bg-cyan-950/60 text-cyan-400 border border-cyan-800/40 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="users" class="w-6 h-6"></i>
        </div>
        <p class="text-sm font-bold text-white">У вас пока нет доступных комнат</p>
        <p class="mt-1 text-xs text-slate-400 leading-relaxed max-w-xs mx-auto">
          Создайте новую комнату или добавьте бота @Xakatonsberbot в чат Telegram!
        </p>
        <button type="button" class="mt-4 px-4 py-2.5 rounded-xl bg-[#00D29D] text-[#06281E] text-xs font-extrabold shadow-card hover:bg-[#00E599] transition-all" onclick="openCreateRoomSheet()">
          + Создать комнату
        </button>
      </div>
    `;
  }
  refreshIcons();
}

// ── Tab & Navigation Switching ──────────────────────────────
const MODE_SCREEN_MAP = {
  manual: 'screen-manual-input',
  text: 'screen-text-input',
  voice: 'screen-voice-input',
  receipt: 'screen-scan-receipt',
  doc: 'screen-upload-doc'
};

function switchTab(tabName) {
  const analyticsResultsRequested = tabName === 'family';
  if (analyticsResultsRequested) tabName = 'analytics';
  if (state.activeSheet) {
    closeSheets(true);
  }
  state.currentTab = tabName;

  // Ensure any input mode screen is hidden when switching tabs
  if (state.activeInputMode) {
    state.activeInputMode = null;
    const inputContainer = document.getElementById('inputScreensContainer');
    if (inputContainer) inputContainer.classList.add('hidden');
    document.querySelectorAll('.input-mode-screen').forEach(scr => scr.classList.add('hidden'));
    const bottomNav = document.getElementById('bottomNav');
    if (bottomNav) bottomNav.classList.remove('hidden');
    if (tg?.BackButton) {
      try { tg.BackButton.hide(); } catch (e) {}
    }
  }

  document.querySelectorAll('.screen-pane').forEach(p => p.classList.add('hidden'));
  const target = document.getElementById(`screen-${tabName}`);
  if (target) target.classList.remove('hidden');

  document.querySelectorAll('.nav-btn').forEach(btn => {
    const t = btn.getAttribute('data-tab');
    if (t === tabName) {
      btn.classList.add('active', 'text-[#00E599]');
      btn.classList.remove('text-slate-400');
    } else {
      btn.classList.remove('active', 'text-[#00E599]');
      btn.classList.add('text-slate-400');
    }
  });

  window.scrollTo(0, 0);
  refreshIcons();

  if (tabName === 'analytics') {
    fetchAnalytics();
    setAnalyticsSubview(analyticsResultsRequested ? 'results' : (state.analyticsSubview || 'overview'));
  }
  if (tabName === 'history') {
    void fetchHistoryExpenses();
  }
  if (tabName === 'plan') {
    fetchPlan();
  }
}

async function fetchPlan() {
  if (!state.groupId) return;
  try {
    let url = `/api/group/${state.groupId}/plan`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    const res = await fetch(url, { headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.planData = await res.json();
    renderPlan();
  } catch (err) {
    console.error('Failed to fetch plan:', err);
    const summary = document.getElementById('planBudgetSummary');
    if (summary) summary.textContent = 'Не удалось загрузить план. Попробуйте ещё раз.';
  }
}

function renderPlan() {
  const data = state.planData;
  if (!data) return;
  const budget = Number(data.budget || 0);
  const spent = Number(data.total_spent || 0);
  const recurring = Number(data.recurring_total || 0);
  const remaining = budget - spent - recurring;
  const budgetSummary = document.getElementById('planBudgetSummary');
  if (budgetSummary) budgetSummary.textContent = `Остаток: ${formatCurrency(Math.max(remaining, 0))} · потрачено ${formatCurrency(spent)}`;

  const categorySummary = document.getElementById('planCategorySummary');
  const limits = data.category_budgets || [];
  if (categorySummary) {
    categorySummary.textContent = limits.length
      ? `${limits.length} ${pluralize(limits.length, 'лимит', 'лимита', 'лимитов')} · нажмите для изменения`
      : 'Нажмите, чтобы задать первый лимит';
  }

  const recurringSummary = document.getElementById('planRecurringSummary');
  const recurringItems = data.recurring_expenses || [];
  if (recurringSummary) {
    recurringSummary.textContent = recurringItems.length
      ? `${recurringItems.length} ${pluralize(recurringItems.length, 'платёж', 'платежа', 'платежей')} · ${formatCurrency(recurring)} в месяц`
      : 'Добавьте подписку или регулярный платёж';
  }

  const firstTip = (data.recommendations || [])[0];
  const tipTitle = document.getElementById('planTipTitle');
  const tipText = document.getElementById('planTipText');
  if (tipTitle) tipTitle.textContent = firstTip?.title || 'Умный планировщик';
  if (tipText) tipText.textContent = firstTip?.text || 'Добавьте лимиты категорий — SberWise подскажет, как распределить бюджет.';
}

function pluralize(value, one, few, many) {
  const n = Math.abs(value) % 100;
  const last = n % 10;
  if (n > 10 && n < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}

async function savePlanBudget() {
  const current = state.planData?.budget || 0;
  const value = window.prompt('Месячный бюджет комнаты, ₽', String(Math.round(current)));
  if (value === null) return;
  const budget = Number(String(value).replace(/\s/g, '').replace(',', '.'));
  if (!Number.isFinite(budget) || budget <= 0) return showToast('Введите сумму больше нуля', 'error');
  const res = await fetch(`/api/group/${state.groupId}/budget`, {
    method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({ budget })
  });
  if (!res.ok) return showToast('Не удалось сохранить бюджет', 'error');
  showToast('Бюджет месяца сохранён', 'success');
  fetchPlan();
}

async function savePlanCategoryBudget() {
  const category = window.prompt('Категория лимита', state.planData?.category_budgets?.[0]?.category || 'Продукты');
  if (!category?.trim()) return;
  const existing = state.planData?.category_budgets?.find(item => item.category === category.trim());
  const value = window.prompt(`Лимит для «${category.trim()}», ₽`, existing ? String(Math.round(existing.limit)) : '10000');
  if (value === null) return;
  const monthly_limit = Number(String(value).replace(/\s/g, '').replace(',', '.'));
  if (!Number.isFinite(monthly_limit) || monthly_limit <= 0) return showToast('Введите сумму больше нуля', 'error');
  const res = await fetch(`/api/group/${state.groupId}/plan/category-budget`, {
    method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({ category: category.trim(), monthly_limit })
  });
  if (!res.ok) return showToast('Не удалось сохранить лимит', 'error');
  showToast('Лимит категории сохранён', 'success');
  fetchPlan();
}

async function addPlanRecurringExpense() {
  const title = window.prompt('Название регулярного платежа', 'Подписка');
  if (!title?.trim()) return;
  const value = window.prompt('Сумма в месяц, ₽', '0');
  if (value === null) return;
  const amount = Number(String(value).replace(/\s/g, '').replace(',', '.'));
  if (!Number.isFinite(amount) || amount <= 0) return showToast('Введите сумму больше нуля', 'error');
  const category = window.prompt('Категория', 'Подписки') || 'Подписки';
  const res = await fetch(`/api/group/${state.groupId}/plan/recurring`, {
    method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({ title: title.trim(), amount, category: category.trim() })
  });
  if (!res.ok) return showToast('Не удалось добавить платёж', 'error');
  showToast('Регулярный платёж добавлен', 'success');
  fetchPlan();
}

function setAnalyticsSubview(view) {
  state.analyticsSubview = view === 'results' ? 'results' : 'overview';
  const overview = document.getElementById('analyticsOverviewContent');
  const results = document.getElementById('screen-family');
  if (overview) overview.classList.toggle('hidden', state.analyticsSubview === 'results');
  if (results) results.classList.toggle('hidden', state.analyticsSubview !== 'results');
  document.querySelectorAll('.analytics-subtab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.analyticsView === state.analyticsSubview);
  });
  if (state.analyticsSubview === 'results' && state.groupId) fetchAndRenderDebts();
  refreshIcons();
}

function setupAnalyticsSubtabs() {
  const host = document.getElementById('analyticsResultsHost');
  const results = document.getElementById('screen-family');
  if (host && results && results.parentElement !== host) host.appendChild(results);
  document.querySelectorAll('.analytics-subtab').forEach(btn => {
    btn.addEventListener('click', () => setAnalyticsSubview(btn.dataset.analyticsView));
  });
}

// ── Full-Screen Input Modes Architecture ─────────────────────
function openInputMode(mode) {
  closeSheets();
  state.activeInputMode = mode;

  // Stop any active camera if switching away from receipt mode
  if (mode !== 'receipt') {
    stopReceiptCamera();
  }

  // Hide bottom nav bar so screen gets 100% height and actions are pinned
  const bottomNav = document.getElementById('bottomNav');
  if (bottomNav) bottomNav.classList.add('hidden');

  // Show full screen input container
  const inputContainer = document.getElementById('inputScreensContainer');
  if (inputContainer) inputContainer.classList.remove('hidden');

  // Hide all other input mode screens
  document.querySelectorAll('.input-mode-screen').forEach(scr => {
    scr.classList.add('hidden');
  });

  // Activate only the selected input mode screen
  const targetId = MODE_SCREEN_MAP[mode] || `screen-${mode}-input`;
  const targetScreen = document.getElementById(targetId);
  if (targetScreen) {
    targetScreen.classList.remove('hidden');
  }

  // Telegram Mini App native BackButton
  if (tg?.BackButton) {
    try {
      tg.BackButton.show();
    } catch (e) {}
  }

  // Preserve & autofocus text if in text mode
  if (mode === 'text') {
    const rawInput = document.getElementById('rawExpenseTextInput');
    if (rawInput && state.textExpenseDraft) {
      rawInput.value = state.textExpenseDraft;
    } else if (rawInput) {
      rawInput.value = '';
      resetTextInputPreview();
    }
  }

  // Initialize receipt camera on entering receipt mode, or reset voice
  if (mode === 'receipt') {
    startReceiptCamera();
  } else {
    stopReceiptCamera();
  }

  if (mode === 'voice') {
    resetVoiceRecording();
  } else {
    stopVoiceMicrophone();
  }

  if (mode === 'doc') {
    resetDocumentImportUi();
  }

  window.scrollTo(0, 0);
  refreshIcons();
}

function navigateBackFromInputMode() {
  if (state.activeInputMode === 'text') {
    const rawInput = document.getElementById('rawExpenseTextInput');
    if (rawInput) state.textExpenseDraft = rawInput.value;
  }

  // Ensure camera and microphone are stopped when navigating back
  stopReceiptCamera();
  stopVoiceMicrophone();

  state.activeInputMode = null;

  // Hide input screens container and all child screens
  const inputContainer = document.getElementById('inputScreensContainer');
  if (inputContainer) inputContainer.classList.add('hidden');
  document.querySelectorAll('.input-mode-screen').forEach(scr => {
    scr.classList.add('hidden');
  });

  // Restore bottom navigation bar
  const bottomNav = document.getElementById('bottomNav');
  if (bottomNav) bottomNav.classList.remove('hidden');

  // Hide native Telegram BackButton
  if (tg?.BackButton) {
    try {
      tg.BackButton.hide();
    } catch (e) {}
  }

  // Return to Add Expense Bottom Sheet menu as expected
  openSheet('sheet-add-picker');
  refreshIcons();
}

function exitAddExpenseFlow(successMsg) {
  stopReceiptCamera();
  stopVoiceMicrophone();
  state.activeInputMode = null;
  state.textExpenseDraft = '';
  state.lastParsedTextDraft = null;
  state.lastParsedTextSource = '';
  state.capturedReceiptBlob = null;
  state.parsedReceiptDraft = null;
  state.capturedVoiceBlob = null;
  state.parsedVoiceDraft = null;

  const inputContainer = document.getElementById('inputScreensContainer');
  if (inputContainer) inputContainer.classList.add('hidden');
  document.querySelectorAll('.input-mode-screen').forEach(scr => {
    scr.classList.add('hidden');
  });

  const bottomNav = document.getElementById('bottomNav');
  if (bottomNav) bottomNav.classList.remove('hidden');

  if (tg?.BackButton) {
    try {
      tg.BackButton.hide();
    } catch (e) {}
  }

  closeSheets();
  switchTab('overview');

  if (successMsg) {
    showToast(successMsg, 'success');
  }
}

// ── Bottom Sheets Logic ─────────────────────────────────────
function roomHasEnoughActiveMembers() {
  const members = state.summary?.members || [];
  return members.filter(member => (member.status || 'active') === 'active' && !member.is_external).length >= 2;
}

function openSheet(sheetId) {
  if (sheetId === 'sheet-add-picker' && state.summary && !roomHasEnoughActiveMembers()) {
    showToast('Чтобы добавить общий расход, сначала пригласите ещё одного участника в комнату', 'info');
    return;
  }
  const overlay = document.getElementById('sheetOverlay');
  const sheets = document.querySelectorAll('.sheet-content');
  const picker = document.getElementById('sheet-add-picker');

  // Notifications is a global overlay and may stack over the add-expense picker.
  sheets.forEach(s => {
    if (sheetId === 'sheet-notifications' && s === picker) return;
    s.classList.remove('active');
    s.classList.add('hidden');
  });

  const target = document.getElementById(sheetId);
  if (!overlay || !target) return;

  // Presentation-only: keep the add-expense header in sync with the active room.
  if (sheetId === 'sheet-add-picker') {
    const currentGroup = state.availableGroups?.find(g => Number(g.id) === Number(state.groupId));
    const roomName = currentGroup?.name || state.summary?.group_name;
    const roomNameEl = target.querySelector('#addExpenseRoomName');
    if (roomNameEl && roomName) roomNameEl.textContent = roomName;
  }

  state.activeSheet = sheetId;
  overlay.classList.remove('hidden');
  void overlay.offsetWidth;
  overlay.classList.add('active');

  target.classList.remove('hidden');
  void target.offsetWidth;
  target.classList.add('active');

  refreshIcons();
}

function closeSheets(closeAll = false) {
  if (state.createRoomScreenOpen) {
    hideCreateRoomScreen();
    return;
  }
  const closingSheet = state.activeSheet;
  const returnToWelcome = closingSheet === 'sheet-create-room' && state.returnToWelcomeOnCreate;
  const notification = document.getElementById('sheet-notifications');

  // Closing the global notifications overlay must not close the sheet beneath it.
  if (!closeAll && closingSheet === 'sheet-notifications' && notification?.classList.contains('active')) {
    closeNotifications();
    return;
  }

  if (closingSheet === 'sheet-notifications') state.notificationsOpen = false;
  state.activeSheet = null;
  const overlay = document.getElementById('sheetOverlay');
  const activeSheets = document.querySelectorAll('.sheet-content.active');
  activeSheets.forEach(s => s.classList.remove('active'));

  if (overlay) {
    overlay.classList.remove('active');
    setTimeout(() => {
      overlay.classList.add('hidden');
      document.querySelectorAll('.sheet-content').forEach(s => {
        s.classList.remove('active');
        s.classList.add('hidden');
      });
      if (returnToWelcome) {
        state.returnToWelcomeOnCreate = false;
        document.getElementById('mainContent')?.classList.add('hidden');
        document.getElementById('bottomNav')?.classList.add('hidden');
        ensureWelcomeScreen().classList.remove('hidden');
      }
    }, 220);
  }
}

// Room Switcher Sheet («Мои комнаты»)
function openGroupSelectorSheet() {
  const container = document.getElementById('groupsListContainer');
  if (!container) return;

  const groups = state.availableGroups || [];
  if (groups.length === 0) {
    container.innerHTML = `
      <div class="py-4 text-center text-xs text-slate-400">
        У вас пока нет доступных комнат.
      </div>
    `;
    openSheet('sheet-groups');
    return;
  }

  container.innerHTML = groups.map(g => {
    const isActive = Number(g.id) === Number(state.groupId);
    const isOneTime = isOneTimeRoom(g);
    const typeLabel = getRoomTypeLabel(g);
    const typeClass = isOneTime ? 'bg-amber-950/60 text-amber-300 border border-amber-800/40' : 'bg-cyan-950/60 text-cyan-300 border border-cyan-800/40';

    return `
      <div class="group-select-card flex items-center justify-between gap-2 p-3.5 rounded-2xl border ${isActive ? 'border-cyan-500 bg-cyan-950/40' : 'border-[#222E46] bg-[#151D2E]'} cursor-pointer hover:bg-[#1C263B] transition-colors shadow-card" data-group-id="${g.id}">
        <div class="flex items-center gap-3">
          <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-800 text-white font-extrabold text-sm border border-slate-700">
            ${(g.name || 'R')[0]}
          </span>
          <div>
            <div class="flex items-center gap-1.5">
              <p class="text-xs font-extrabold text-white">${g.name}</p>
              <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${typeClass}">${typeLabel}</span>
            </div>
            <p class="text-[11px] text-slate-400 mt-0.5">${formatCurrency(g.total_expenses || 0, g.currency)} · ${g.members_count || 1} уч.</p>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          ${isActive ? '<i data-lucide="check" class="w-5 h-5 text-[#00E599]"></i>' : ''}
          <button type="button" class="btn-delete-group flex h-9 w-9 items-center justify-center rounded-xl border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20" data-delete-group-id="${g.id}" data-delete-group-name="${escapeHtml(g.name || 'Комната')}" data-delete-scope="${g.can_delete_room ? 'room' : 'self'}" aria-label="Удалить комнату"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.group-select-card').forEach(card => {
    card.addEventListener('click', async () => {
      const gid = card.getAttribute('data-group-id');
      if (gid) {
        state.groupId = gid;
        state.analyticsData = null;
        closeSheets();
        await fetchSummary();
        await fetchAnalytics();
      }
    });
  });
  container.querySelectorAll('.btn-delete-group').forEach(button => {
    button.addEventListener('click', event => {
      event.stopPropagation();
      state.groupId = Number(button.dataset.deleteGroupId);
      state.summary = { ...(state.summary || {}), group_name: button.dataset.deleteGroupName, can_delete_room: true };
      state.pendingRoomDeletionScope = button.dataset.deleteScope;
      openDeleteRoomConfirmation();
    });
  });

  openSheet('sheet-groups');
  refreshIcons();
}

function setPrimaryAppVisible(visible) {
  const mainContent = document.getElementById('mainContent');
  const bottomNav = document.getElementById('bottomNav');
  mainContent?.classList.toggle('hidden', !visible);
  bottomNav?.classList.toggle('hidden', !visible);
  if (visible) {
    mainContent?.removeAttribute('hidden');
    bottomNav?.removeAttribute('hidden');
    if (mainContent) mainContent.style.display = '';
    if (bottomNav) bottomNav.style.display = '';
  } else {
    mainContent?.setAttribute('hidden', '');
    bottomNav?.setAttribute('hidden', '');
  }
}

function openCreateRoomScreen(origin = 'app') {
  const screen = document.getElementById('sheet-create-room');
  const appShell = document.getElementById('appShell');
  if (!screen || !appShell) return;

  // Reuse the existing form and submit handler.  Only its presentation changes.
  appShell.appendChild(screen);
  state.createRoomScreenOpen = true;
  state.createRoomOrigin = origin;
  document.getElementById('welcomeScreen')?.classList.add('hidden');
  setPrimaryAppVisible(false);
  screen.classList.add('create-room-screen');
  screen.classList.remove('hidden', 'active', 'translate-y-full');
  screen.removeAttribute('aria-hidden');
  updateCreateRoomParticipantsUI();
  refreshIcons();
}

function hideCreateRoomScreen({ returnToOrigin = true } = {}) {
  const screen = document.getElementById('sheet-create-room');
  if (screen) {
    screen.classList.remove('create-room-screen', 'active');
    screen.classList.add('hidden', 'translate-y-full');
  }
  const origin = state.createRoomOrigin;
  state.createRoomScreenOpen = false;
  state.createRoomOrigin = null;

  if (!returnToOrigin) return;
  if (origin === 'welcome') {
    setPrimaryAppVisible(false);
    ensureWelcomeScreen().classList.remove('hidden');
  } else {
    setPrimaryAppVisible(true);
  }
}

// Kept as the public entry point for buttons elsewhere in the app.
function openCreateRoomSheet() {
  openCreateRoomScreen('app');
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
        <span class="text-xs font-bold text-white">Вы <span class="ml-1 font-medium text-slate-400">Создатель</span></span>
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
      // Telegram can show its native contact chooser only for a real share link.
      // The room ID exists after creation, so defer sharing until the form succeeds.
      state.createRoomInviteAfterCreate = true;
      showToast('После создания комнаты откроется список контактов Telegram', 'info');
    });
  }

  // 5. Submit Form
  const formCreate = document.getElementById('formCreateRoomFigma');
  if (formCreate) {
    formCreate.addEventListener('submit', async (e) => {
      e.preventDefault();
      const nameInp = document.getElementById('createRoomNameInput');
      const roomName = (nameInp?.value || '').trim();
      if (!roomName) return showToast('Укажите название комнаты', 'error');
      const submitButton = formCreate.querySelector('[type="submit"]');
      if (submitButton?.disabled) return;
      if (submitButton) { submitButton.disabled = true; submitButton.classList.add('opacity-60'); }
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
        if (!createdId) throw new Error('Сервер не вернул ID комнаты');
        const inviteRes = await fetch(appendTgUserId(`/api/rooms/${createdId}/invites`), { method: 'POST', headers: getRequestHeaders() });
        const inviteData = await inviteRes.json().catch(() => ({}));
        if (!inviteRes.ok || !inviteData.invite_link) throw new Error(inviteData.error || 'Не удалось создать приглашение');
        hideCreateRoomScreen({ returnToOrigin: false });
        const groupsRes = await fetchUserGroupsList();
        state.availableGroups = groupsRes.groups || [];
        showRoomCreatedScreen({ roomId: createdId, roomName, inviteLink: inviteData.invite_link });
      } catch (err) {
        console.error('Failed to create room:', err);
        showToast(err.message || 'Ошибка при создании комнаты', 'error');
      } finally {
        if (submitButton) { submitButton.disabled = false; submitButton.classList.remove('opacity-60'); }
      }
    });
  }

  updateCreateRoomParticipantsUI();
}

function showRoomCreatedScreen({ roomId, roomName, inviteLink }) {
  document.getElementById('roomCreatedScreen')?.remove();
  const screen = document.createElement('div');
  screen.id = 'roomCreatedScreen';
  screen.className = 'room-created-screen';
  screen.innerHTML = `
    <header class="room-create-screen-header"><button id="roomCreatedClose" type="button" class="room-create-back" aria-label="Перейти в комнату"><i data-lucide="arrow-left" class="h-5 w-5"></i></button><h2>Комната создана</h2><span></span></header>
    <section class="room-created-content">
      <div class="room-created-icon"><i data-lucide="check-circle-2" class="h-8 w-8"></i></div>
      <p class="room-created-kicker">ГОТОВО</p>
      <h1>${escapeHtml(roomName)}</h1>
      <p>Пригласите участников — они присоединятся только после подтверждения.</p>
      <div class="room-created-actions">
        <button id="roomCreatedShare" class="room-created-primary"><i data-lucide="send" class="h-4 w-4"></i> Пригласить через Telegram</button>
        <button id="roomCreatedCopy" class="room-created-secondary"><i data-lucide="copy" class="h-4 w-4"></i> Скопировать ссылку</button>
        <button id="roomCreatedOpen" class="room-created-link">Перейти в комнату <i data-lucide="arrow-right" class="h-4 w-4"></i></button>
      </div>
    </section>`;
  document.getElementById('appShell')?.appendChild(screen);
  screen.querySelector('#roomCreatedShare').addEventListener('click', () => requestRoomInviteDelivery(roomId));
  screen.querySelector('#roomCreatedCopy').addEventListener('click', async () => { await navigator.clipboard?.writeText(inviteLink); showToast('Ссылка-приглашение скопирована', 'success'); });
  const goToRoom = async () => {
    screen.remove();
    document.getElementById('welcomeScreen')?.remove();
    setPrimaryAppVisible(true);
    state.groupId = roomId;
    await fetchSummary();
  };
  screen.querySelector('#roomCreatedOpen').addEventListener('click', goToRoom);
  screen.querySelector('#roomCreatedClose').addEventListener('click', goToRoom);
  refreshIcons();
}


// ── Room Settlement («Итоги комнаты») ───────────────────────
// ==============================================================================
// FIGMA CORE SCREENS INTERACTIVE LOGIC (Screens 1 - 5)
// ==============================================================================

// Screen 1: «Итоги комнаты»
async function openRoomSettlementSheet() {
  if (!state.groupId) return;
  if (state.isOpeningRoomSettlement) return;
  state.isOpeningRoomSettlement = true;

  const transfersCount = document.getElementById('settlementTransfersCount');
  const transfersList = document.getElementById('settlementTransfersList');
  if (transfersCount) transfersCount.textContent = 'Загружаем итоги…';
  if (transfersList) {
    transfersList.innerHTML = '<div class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-5 text-center text-xs text-slate-400">Загружаем расчёты комнаты…</div>';
  }
  // Give the tap an immediate, visible response even on a slow Telegram connection.
  openSheet('sheet-room-settlement');
  refreshIcons();

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
    // API exposes the current participant's balance as `my_result`.
    // Keep the old field as a compatibility fallback, but never turn a
    // negative/positive balance into zero just because the field name differs.
    const pres = Number(data.my_result ?? data.personal_result ?? 0);
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
    const transfersTotal = transfers.reduce((sum, transfer) => sum + Number(transfer.amount || 0), 0);
    if (transfersCount) transfersCount.textContent = transfers.length ? `${transfers.length} · ${formatCurrency(transfersTotal)} к переводу` : 'Переводов нет';

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
                  <p class="text-xs font-bold text-white">${t.from_name} → ${t.to_name}</p>
                  <p class="text-[11px] text-slate-400 mt-0.5">Нужно перевести для закрытия расчёта</p>
                </div>
              </div>
              <button type="button" class="px-3 py-1.5 rounded-xl bg-[#00D29D]/20 text-[#00E599] border border-[#00D29D]/30 font-black text-xs hover:bg-[#00D29D]/30 active:scale-95 transition-all" onclick="openSettlementSheet({from_name: '${t.from_name}', to_name: '${t.to_name}', amount: ${t.amount}})"><span class="block text-[9px] opacity-75">К переводу</span>${formatCurrency(t.amount, data.currency)}</button>
            </div>
          `;
        }).join('');
      }
    }

    refreshIcons();
  } catch (err) {
    console.error('Failed to load room settlement:', err);
    if (transfersCount) transfersCount.textContent = 'Не удалось загрузить';
    if (transfersList) {
      transfersList.innerHTML = '<div class="rounded-2xl border border-rose-500/35 bg-rose-950/20 p-5 text-center"><p class="text-sm font-black text-rose-200">Не удалось загрузить итоги</p><button type="button" class="mt-3 rounded-xl border border-[#00D29D]/40 bg-[#00D29D]/15 px-3 py-2 text-xs font-black text-[#00E599]" onclick="openRoomSettlementSheet()">Повторить</button></div>';
    }
    showToast('Не удалось загрузить итоги комнаты', 'error');
  } finally {
    state.isOpeningRoomSettlement = false;
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
  if (!await showAppConfirm('Завершить комнату?', 'Финальный расчёт будет зафиксирован, а комната перейдёт в архив.', 'Завершить')) return;
  try {
    let url = `/api/group/${state.groupId}/archive`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }
    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    closeSheets();
    await fetchSummary();
  } catch (err) {
    console.error('Failed to archive room:', err);
    showToast('Ошибка закрытия комнаты', 'error');
  }
}

// Screen 2: «Импорт электронного чека (PDF/CSV)»
function getDocumentSplitMembers() {
  return (state.summary?.members || []).filter(member => state.documentParticipantIds.includes(member.id));
}

function setDocumentImportStatus(text = '', tone = 'idle') {
  const status = document.getElementById('docParseStatus');
  if (!status) return;
  const label = status.querySelector('span:last-child');
  if (!text) {
    status.className = 'hidden text-xs font-bold mt-1 flex items-center gap-1';
    if (label) label.textContent = '';
    return;
  }
  const color = tone === 'error' ? 'text-rose-300' : tone === 'loading' ? 'text-indigo-300' : 'text-mint-400';
  status.className = `text-xs font-bold ${color} mt-1 flex items-center gap-1`;
  if (label) label.textContent = text;
}

function setDocumentPrimaryAction(text, disabled = false) {
  const button = document.getElementById('btnParseDocSubmit');
  if (!button) return;
  button.textContent = text;
  button.disabled = disabled;
  button.classList.toggle('opacity-60', disabled);
}

function resetDocumentImportUi() {
  state.selectedDocFile = null;
  state.parsedDocumentDraft = null;
  state.documentParticipantIds = [];
  const input = document.getElementById('docFileInput');
  if (input) input.value = '';
  const name = document.getElementById('docFileName');
  const size = document.getElementById('docFileSize');
  const service = document.getElementById('docServiceName');
  const dates = document.getElementById('docServiceDates');
  const total = document.getElementById('docTotalAmountDisplay');
  if (name) name.textContent = 'Выберите PDF или CSV';
  if (size) size.textContent = 'Поддерживаются PDF и CSV до 20 МБ';
  if (service) service.textContent = 'Документ ещё не загружен';
  if (dates) dates.textContent = '—';
  if (total) total.textContent = '— ₽';
  setDocumentImportStatus();
  setDocumentPrimaryAction('Выбрать PDF или CSV');
  renderDocumentParticipants();
}

function openDeleteRoomConfirmation() {
  const confirmButton = document.getElementById('btnConfirmDeleteRoom');
  if (confirmButton) { confirmButton.disabled = false; confirmButton.textContent = 'Удалить'; }
  const roomName = state.summary.group_name || 'эту комнату';
  const text = document.getElementById('deleteRoomConfirmationText');
  const selfOnly = state.pendingRoomDeletionScope === 'self';
  if (text) text.textContent = selfOnly ? `Убрать комнату «${roomName}» только у вас? Комната и данные остальных участников сохранятся.` : `Удалить комнату «${roomName}»? Все данные комнаты будут удалены. Это действие нельзя отменить.`;
  openSheet('sheet-delete-room');
}

async function handleDeleteRoom() {
  if (state.deletingRoom || !state.groupId) return;
  const button = document.getElementById('btnConfirmDeleteRoom');
  const deletedRoomId = Number(state.groupId);
  const deleteScope = state.pendingRoomDeletionScope || 'room';
  state.deletingRoom = true;
  if (button) { button.disabled = true; button.textContent = 'Удаляем…'; }
  try {
    let url = `/api/rooms/${deletedRoomId}${deleteScope === 'self' ? '/membership' : ''}`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    const res = await fetch(url, { method: 'DELETE', headers: getRequestHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

    const groupsRes = await fetchUserGroupsList();
    state.availableGroups = groupsRes.groups || [];
    state.analyticsData = null;
    state.summary = null;
    const nextRoom = state.availableGroups.find(group => Number(group.id) !== deletedRoomId);
    state.pendingRoomDeletionScope = null;
    if (nextRoom) {
      state.groupId = nextRoom.id;
      openGroupSelectorSheet();
      void fetchSummary();
    } else {
      closeSheets(true);
      state.groupId = 0;
      setPrimaryAppVisible(false);
      ensureWelcomeScreen().classList.remove('hidden');
    }
    showToast('Комната удалена', 'success');
  } catch (err) {
    console.error('Failed to delete room:', err);
    showToast(err.message || 'Не удалось удалить комнату', 'error');
    if (button) { button.disabled = false; button.textContent = 'Удалить'; }
  } finally {
    state.deletingRoom = false;
  }
}

function updateDocumentSplitUi() {
  const draft = state.parsedDocumentDraft;
  const selectedMembers = getDocumentSplitMembers();
  const countEl = document.getElementById('docParticipantsCount');
  const labelEl = document.getElementById('docSplitLabel');
  const shareEl = document.getElementById('docMyShareDisplay');
  const currency = draft?.currency || 'RUB';
  const count = selectedMembers.length;
  if (countEl) countEl.textContent = `${count} ${count === 1 ? 'чел.' : 'чел.'}`;
  if (labelEl) labelEl.textContent = count ? `Поровну на ${count} ${count === 1 ? 'человека' : 'человек'}` : 'Выберите участников';
  if (shareEl) shareEl.textContent = count && draft ? formatCurrency(Number(draft.total_amount || 0) / count, currency) : '— ₽';
}

function renderDocumentParticipants() {
  const container = document.getElementById('docParticipantsContainer');
  if (!container) return;
  const members = state.summary?.members || [];
  if (!members.length) {
    container.innerHTML = '<p class="text-xs text-slate-500">Участники комнаты не найдены</p>';
    updateDocumentSplitUi();
    return;
  }
  container.innerHTML = members.map(member => {
    const selected = state.documentParticipantIds.includes(member.id);
    const name = escapeHtml(member.name || member.display_name || 'Участник');
    return `<button type="button" data-doc-participant-id="${member.id}" class="doc-participant-toggle inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition-all ${selected ? 'border-mint-500/60 bg-mint-500/15 text-mint-300' : 'border-[#334155] bg-[#0E1422] text-slate-300'}"><span class="flex h-5 w-5 items-center justify-center rounded-full ${selected ? 'bg-mint-500 text-[#06281E]' : 'border border-slate-500 text-transparent'}">✓</span><span>${name}</span></button>`;
  }).join('');
  container.querySelectorAll('[data-doc-participant-id]').forEach(button => {
    button.addEventListener('click', () => {
      const memberId = Number(button.dataset.docParticipantId);
      if (state.documentParticipantIds.includes(memberId)) {
        state.documentParticipantIds = state.documentParticipantIds.filter(id => id !== memberId);
      } else {
        state.documentParticipantIds = [...state.documentParticipantIds, memberId];
      }
      renderDocumentParticipants();
    });
  });
  updateDocumentSplitUi();
}

async function handleParseDocument() {
  if (!state.selectedDocFile) {
    const docInput = document.getElementById('docFileInput');
    if (docInput) {
      docInput.click();
      return;
    }
  }

  setDocumentImportStatus('Распознаём документ…', 'loading');
  setDocumentPrimaryAction('Распознаём…', true);
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

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    const draft = data.draft;
    if (!draft || !Array.isArray(draft.items) || draft.items.length === 0 || Number(draft.total_amount || 0) <= 0) {
      throw new Error('В документе не найдены сумма или позиции. Проверьте PDF и попробуйте снова.');
    }
    state.parsedDocumentDraft = draft;
    state.documentParticipantIds = (state.summary?.members || []).map(member => member.id);

    // Update Document Card details
    const parsed = draft;
    const sName = document.getElementById('docServiceName');
    const sDates = document.getElementById('docServiceDates');
    const totalEl = document.getElementById('docTotalAmountDisplay');
    
    if (sName) sName.textContent = parsed.merchant || parsed.title || 'Не определено';
    if (sDates) sDates.textContent = parsed.date || 'Дата не найдена';
    if (totalEl) totalEl.textContent = formatCurrency(parsed.total_amount, parsed.currency || 'RUB');
    renderDocumentParticipants();
    setDocumentImportStatus('Файл проверен и распознан');
    setDocumentPrimaryAction('Добавить расход');
    
    showToast('Файл успешно проверен и распарсен!', 'success');
  } catch (err) {
    state.parsedDocumentDraft = null;
    state.documentParticipantIds = [];
    renderDocumentParticipants();
    setDocumentImportStatus('Не удалось распознать файл. Попробуйте другой документ.', 'error');
    setDocumentPrimaryAction('Повторить распознавание');
    console.error('Error parsing document:', err);
    showToast('Не удалось прочитать документ: ' + (err.message || 'неизвестная ошибка'), 'error');
  }
}

async function handleConfirmAttachDoc() {
  if (!state.groupId) return;
  const draft = state.parsedDocumentDraft;
  if (!draft || !Array.isArray(draft.items) || !draft.items.length) {
    showToast('Сначала загрузите и распознайте документ', 'error');
    return;
  }
  const participantIds = state.documentParticipantIds.filter(id => (state.summary?.members || []).some(member => member.id === id));
  if (!participantIds.length) {
    showToast('Выберите хотя бы одного участника для разделения расхода', 'error');
    return;
  }
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: draft.title || draft.merchant || 'Импортированный расход',
        amount: draft.total_amount,
        category: draft.items[0]?.category || '🔧 Другое',
        payer_id: state.currentUser?.id || null,
        split_type: 'equal',
        source_type: draft.source_type || 'pdf',
        currency: draft.currency || 'RUB',
        items: draft.items.map(item => ({ ...item, participants: [...participantIds] })),
        attachment: {
          filename: state.selectedDocFile?.name || 'document.pdf',
          file_type: state.selectedDocFile?.type || 'application/pdf',
          file_size: state.selectedDocFile?.size || 0
        }
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    exitAddExpenseFlow(`Расход ${formatCurrency(draft.total_amount, draft.currency || 'RUB')} успешно добавлен в комнату!`);
    await fetchSummary();
  } catch (err) {
    console.error('Failed to attach doc expense:', err);
    showToast('Ошибка прикрепления документа', 'error');
  }
}

// Screen 3: «Текстовый ввод»
function resetTextInputPreview() {
  state.lastParsedTextDraft = null;
  state.lastParsedTextSource = '';
  const pillsContainer = document.getElementById('textParsedPillsContainer');
  const countEl = document.getElementById('textParsedMembersCount');
  const totalEl = document.getElementById('textTotalAmountDisplay');
  const payerEl = document.getElementById('textPayerDisplay');
  if (pillsContainer) pillsContainer.innerHTML = '<span class="px-3 py-1.5 rounded-xl bg-[#1E293B] border border-[#334155] text-xs font-semibold text-slate-400">Участники появятся после распознавания</span>';
  if (countEl) countEl.textContent = '—';
  if (totalEl) totalEl.textContent = '—';
  if (payerEl) payerEl.textContent = '—';
  const submitButton = document.getElementById('btnParseTextSubmit');
  if (submitButton) submitButton.innerHTML = '<i data-lucide="zap" class="w-4 h-4"></i> Рассчитать чек';
  refreshIcons();
}

function renderTextParsedParticipants(draft, roomMembers = []) {
  const pillsContainer = document.getElementById('textParsedPillsContainer');
  const countEl = document.getElementById('textParsedMembersCount');
  if (!pillsContainer || !countEl) return;

  const members = roomMembers.length ? roomMembers : (state.summary?.members || []);
  const memberById = new Map(members.map(member => [String(member.id), member.name || member.display_name || 'Участник']));
  const positionsByMember = new Map();

  (draft.items || []).forEach(item => {
    [...new Set(item.participants || [])].forEach(memberId => {
      const id = String(memberId);
      positionsByMember.set(id, (positionsByMember.get(id) || 0) + 1);
    });
  });

  const participantIds = [...positionsByMember.keys()];
  countEl.textContent = participantIds.length
    ? `${participantIds.length} ${participantIds.length === 1 ? 'участник' : 'участника'}`
    : 'Не определены';

  if (!participantIds.length) {
    pillsContainer.innerHTML = '<span class="px-3 py-1.5 rounded-xl bg-[#1E293B] border border-[#334155] text-xs font-semibold text-slate-400">Не удалось определить участников</span>';
    return;
  }

  pillsContainer.innerHTML = participantIds.map((id, index) => {
    const name = memberById.get(id) || 'Участник комнаты';
    const positions = positionsByMember.get(id);
    const positionWord = positions === 1 ? 'позиция' : (positions < 5 ? 'позиции' : 'позиций');
    const colorClass = index % 2
      ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-300'
      : 'bg-cyan-500/10 border-cyan-500/20 text-cyan-300';
    return `<span class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-bold ${colorClass}"><i data-lucide="user" class="w-3 h-3"></i> ${escapeHtml(name)} (${positions} ${positionWord})</span>`;
  }).join('');
  refreshIcons();
}

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
    const draft = data.draft || data;
    state.lastParsedTextDraft = draft;
    state.lastParsedTextSource = text;

    const totalEl = document.getElementById('textTotalAmountDisplay');
    const payerEl = document.getElementById('textPayerDisplay');
    renderTextParsedParticipants(draft, data.room_members || []);
    if (totalEl) totalEl.textContent = formatCurrency(draft.total_amount || 0, draft.currency || 'RUB');
    if (payerEl) {
      const members = data.room_members || state.summary?.members || [];
      const payer = members.find(member => String(member.id) === String(draft.payer_id));
      payerEl.textContent = payer?.name || payer?.display_name || 'Не указан';
    }

    const submitButton = document.getElementById('btnParseTextSubmit');
    if (submitButton) submitButton.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Сохранить чек';
    refreshIcons();

    showToast('Позиции и персоны успешно определены!', 'success');
  } catch (err) {
    console.error('Error parsing text:', err);
    showToast('Распознано с локальными правилами', 'info');
  }
}

async function handleSaveTextExpense() {
  if (!state.groupId) return;
  const text = (document.getElementById('rawExpenseTextInput')?.value || '').trim();
  if (!state.lastParsedTextDraft || state.lastParsedTextSource !== text) {
    await handleParseText();
    return;
  }
  const draft = state.lastParsedTextDraft;
  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: draft.title || 'Расход',
        amount: draft.total_amount || 0,
        category: draft.items?.[0]?.category || '🔧 Другое',
        payer_id: draft.payer_id || state.currentUser?.id || null,
        split_type: 'itemized',
        items: draft.items || []
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    exitAddExpenseFlow(`Чек на ${formatCurrency(draft.total_amount || 0, draft.currency || 'RUB')} успешно сохранен!`);
    await fetchSummary();
  } catch (err) {
    console.error('Failed to save text expense:', err);
    showToast('Ошибка сохранения расхода', 'error');
  }
}

// ============================================================
// Screen 4: РЕАЛЬНЫЙ СКАНЕР ЧЕКОВ (Live Camera & OCR AI)
// ============================================================

state.scannerState = 'camera'; // 'camera' | 'captured' | 'processing' | 'error' | 'result'
state.activeCameraStream = null;
state.currentCameraFacing = 'environment';
state.capturedReceiptBlob = null;
state.parsedReceiptDraft = null;
state.cameraTrack = null;
state.hasTorch = false;
state.isTorchOn = false;
state.scannerCameraRequestId = 0;
state.isOpeningReceiptCamera = false;
state.isCapturingReceipt = false;
state.isProcessingReceipt = false;
state.receiptPreviewUrl = null;
state.scannerNeedsReopen = false;

function receiptScannerLog(event, details = {}) {
  // Deliberately metadata-only: never log a receipt image or OCR text.
  console.debug('[ReceiptScanner]', event, details);
}

function releaseReceiptPreviewUrl() {
  if (!state.receiptPreviewUrl) return;
  try { URL.revokeObjectURL(state.receiptPreviewUrl); } catch (e) {}
  state.receiptPreviewUrl = null;
}

function setReceiptCaptureDisabled(disabled) {
  const button = document.getElementById('btnCaptureReceiptPhoto');
  if (!button) return;
  button.disabled = Boolean(disabled);
  button.classList.toggle('opacity-50', Boolean(disabled));
  button.classList.toggle('pointer-events-none', Boolean(disabled));
}

function waitForReceiptVideo(video, timeoutMs = 4500) {
  if (video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const onReady = () => finish();
    const timer = setTimeout(() => finish(new Error('Camera preview timed out')), timeoutMs);
    const finish = (error) => {
      clearTimeout(timer);
      video.removeEventListener('loadeddata', onReady);
      video.removeEventListener('loadedmetadata', onReady);
      error ? reject(error) : resolve();
    };
    video.addEventListener('loadeddata', onReady, { once: true });
    video.addEventListener('loadedmetadata', onReady, { once: true });
  });
}

function setScannerState(newState) {
  state.scannerState = newState;
  const states = ['Camera', 'Captured', 'Processing', 'Error', 'Result'];
  states.forEach(s => {
    const el = document.getElementById(`scanState${s}`);
    if (el) {
      if (s.toLowerCase() === newState.toLowerCase()) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
  });

  const bottomBar = document.getElementById('scanResultBottomBar');
  if (bottomBar) {
    if (newState === 'result') {
      bottomBar.classList.remove('hidden');
    } else {
      bottomBar.classList.add('hidden');
    }
  }
  refreshIcons();
}

async function startReceiptCamera() {
  const requestId = ++state.scannerCameraRequestId;
  state.isOpeningReceiptCamera = true;
  setScannerState('camera');

  // Verify secure context for camera access
  if (!window.isSecureContext && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    state.isOpeningReceiptCamera = false;
    showScanError(
      'Требуется защищенное соединение (HTTPS)',
      'Доступ к камере блокируется браузером в небезопасном контексте. Загрузите фото из галереи.'
    );
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    state.isOpeningReceiptCamera = false;
    showScanError(
      'Камера не поддерживается',
      'Ваш браузер или клиент не поддерживает прямой доступ к камере. Используйте кнопку «Из галереи».'
    );
    return;
  }

  stopReceiptCamera({ invalidateRequest: false });

  try {
    const preferredConstraints = {
      video: {
        facingMode: { ideal: state.currentCameraFacing },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      },
      audio: false
    };

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(preferredConstraints);
    } catch (firstError) {
      if (!['OverconstrainedError', 'ConstraintNotSatisfiedError', 'NotFoundError', 'DevicesNotFoundError'].includes(firstError?.name)) throw firstError;
      receiptScannerLog('CAMERA_REAR_FALLBACK', { reason: firstError.name });
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    }
    if (requestId !== state.scannerCameraRequestId) {
      stream.getTracks().forEach(track => track.stop());
      return;
    }
    state.activeCameraStream = stream;

    const videoEl = document.getElementById('receiptCameraVideo');
    if (videoEl) {
      videoEl.srcObject = stream;
      await videoEl.play();
      await waitForReceiptVideo(videoEl);
    } else {
      throw new Error('Receipt preview element is unavailable');
    }
    if (requestId !== state.scannerCameraRequestId) {
      stream.getTracks().forEach(track => track.stop());
      return;
    }

    // Check torch capability
    const track = stream.getVideoTracks()[0];
    state.cameraTrack = track;
    if (track) {
      const caps = track.getCapabilities ? track.getCapabilities() : {};
      state.hasTorch = !!caps.torch;
      const torchBtn = document.getElementById('btnReceiptTorchToggle');
      if (torchBtn) {
        if (state.hasTorch) {
          torchBtn.classList.remove('hidden');
        } else {
          torchBtn.classList.add('hidden');
        }
      }

      // Update resolution label
      const settings = track.getSettings ? track.getSettings() : {};
      const resLabel = document.getElementById('cameraResolutionLabel');
      if (resLabel && settings.width && settings.height) {
        resLabel.textContent = `${settings.width}x${settings.height}`;
      }
      receiptScannerLog('CAMERA_GRANTED', { width: settings.width || 0, height: settings.height || 0, facingMode: settings.facingMode || 'unknown' });
    }
  } catch (err) {
    if (requestId !== state.scannerCameraRequestId) return;
    console.error('Camera access error:', err);
    receiptScannerLog('CAMERA_FAILED', { name: err?.name || 'unknown' });
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showScanError(
        'Доступ к камере запрещён',
        'Для сканирования чека разрешите доступ к камере в настройках браузера или Telegram, либо загрузите фото из галереи.'
      );
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      showScanError(
        'Камера не обнаружена',
        'Устройство не имеет доступной камеры. Выберите фото чека из галереи.'
      );
    } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
      showScanError(
        'Камера занята',
        'Камера используется другим приложением. Закройте другие программы или загрузите фото из галереи.'
      );
    } else if (err?.message === 'Camera preview timed out') {
      showScanError(
        'Камера не передаёт изображение',
        'Закройте сканер и откройте его снова. Если preview остаётся чёрным, выберите фото из галереи.'
      );
    } else {
      showScanError(
        'Не удалось запустить камеру',
        'Произошла ошибка при инициализации камеры. Вы можете выбрать фото из галереи.'
      );
    }
  } finally {
    if (requestId === state.scannerCameraRequestId) state.isOpeningReceiptCamera = false;
  }
}

function stopReceiptCamera({ invalidateRequest = true } = {}) {
  if (invalidateRequest) state.scannerCameraRequestId += 1;
  if (state.activeCameraStream) {
    try {
      state.activeCameraStream.getTracks().forEach(t => t.stop());
    } catch (e) {
      console.warn('Error stopping track:', e);
    }
    state.activeCameraStream = null;
  }
  state.cameraTrack = null;
  state.isTorchOn = false;
  const videoEl = document.getElementById('receiptCameraVideo');
  if (videoEl) {
    try { videoEl.pause(); } catch (e) {}
    videoEl.srcObject = null;
  }
  const torchBtn = document.getElementById('btnReceiptTorchToggle');
  if (torchBtn) {
    torchBtn.classList.add('hidden');
    torchBtn.classList.remove('text-amber-300', 'bg-amber-500/20');
  }
  setReceiptCaptureDisabled(false);
  receiptScannerLog('CAMERA_STOPPED');
}

async function switchReceiptCamera() {
  state.currentCameraFacing = state.currentCameraFacing === 'environment' ? 'user' : 'environment';
  await startReceiptCamera();
}

async function toggleReceiptTorch() {
  if (!state.cameraTrack || !state.hasTorch) return;
  try {
    state.isTorchOn = !state.isTorchOn;
    await state.cameraTrack.applyConstraints({
      advanced: [{ torch: state.isTorchOn }]
    });
    const torchBtn = document.getElementById('btnReceiptTorchToggle');
    if (torchBtn) {
      if (state.isTorchOn) {
        torchBtn.classList.add('text-amber-300', 'bg-amber-500/20');
      } else {
        torchBtn.classList.remove('text-amber-300', 'bg-amber-500/20');
      }
    }
  } catch (err) {
    console.warn('Torch toggle failed:', err);
  }
}

function captureReceiptPhoto() {
  const video = document.getElementById('receiptCameraVideo');
  const canvas = document.getElementById('receiptCaptureCanvas');
  const previewImg = document.getElementById('receiptCapturedPreview');

  if (state.isCapturingReceipt || state.isProcessingReceipt || !video || !canvas || !previewImg) return;
  if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
    showScanError('Камера ещё не готова', 'Подождите появления изображения в preview и повторите снимок.');
    return;
  }
  state.isCapturingReceipt = true;
  setReceiptCaptureDisabled(true);
  const sourceWidth = video.videoWidth;
  const sourceHeight = video.videoHeight;
  // 1600px keeps receipt text readable for OCR but avoids a slow 2–4K JPEG
  // encoding pause on mobile WebViews.
  const scale = Math.min(1, 1600 / Math.max(sourceWidth, sourceHeight));
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));

  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    state.isCapturingReceipt = false;
    setReceiptCaptureDisabled(false);
    showScanError('Ошибка захвата кадра', 'Не удалось подготовить изображение для распознавания.');
    return;
  }
  const stepEl = document.getElementById('scanProcessingStep');
  if (stepEl) stepEl.textContent = 'Подготавливаем чёткий снимок чека…';
  setScannerState('processing');
  ctx.drawImage(video, 0, 0, width, height);

  canvas.toBlob(blob => {
    state.isCapturingReceipt = false;
    setReceiptCaptureDisabled(false);
    if (!blob) {
      showScanError('Ошибка захвата кадра', 'Не удалось получить снимок с камеры.');
      return;
    }
    state.capturedReceiptBlob = blob;
    releaseReceiptPreviewUrl();
    state.receiptPreviewUrl = URL.createObjectURL(blob);
    previewImg.src = state.receiptPreviewUrl;
    receiptScannerLog('CAPTURE_DONE', { sourceWidth, sourceHeight, width, height, bytes: blob.size, mime: blob.type });

    // Critical: Stop camera stream as soon as photo is taken
    stopReceiptCamera();

    // Show captured preview
    setScannerState('captured');
    if (tg?.HapticFeedback) {
      try { tg.HapticFeedback.impactOccurred('medium'); } catch (e) {}
    }
  }, 'image/jpeg', 0.90);
}

function handleReceiptGalleryFile(file) {
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    showScanError('Неверный формат', 'Пожалуйста, выберите файл изображения (JPG, PNG или WebP).');
    return;
  }
  if (file.size > 15 * 1024 * 1024) {
    showScanError('Файл слишком большой', 'Размер изображения не должен превышать 15 МБ.');
    return;
  }

  state.capturedReceiptBlob = file;
  const previewImg = document.getElementById('receiptCapturedPreview');
  if (previewImg) {
    releaseReceiptPreviewUrl();
    state.receiptPreviewUrl = URL.createObjectURL(file);
    previewImg.src = state.receiptPreviewUrl;
  }
  receiptScannerLog('GALLERY_SELECTED', { bytes: file.size, mime: file.type || 'unknown', extension: (file.name || '').split('.').pop()?.toLowerCase() || 'unknown' });
  stopReceiptCamera();
  setScannerState('captured');
}

function showScanError(title, msg, code = 'SCAN_FAILED') {
  stopReceiptCamera();
  receiptScannerLog('SCANNER_ERROR', { code });
  const tEl = document.getElementById('scanErrorTitle');
  const mEl = document.getElementById('scanErrorMessage');
  if (tEl) tEl.textContent = title;
  if (mEl) mEl.textContent = msg;
  setScannerState('error');
}

async function uploadAndProcessReceipt() {
  if (!state.capturedReceiptBlob) {
    showScanError('Фото не найдено', 'Сделайте снимок или загрузите фото чека из галереи.');
    return;
  }

  if (state.isProcessingReceipt) return;
  state.isProcessingReceipt = true;
  setScannerState('processing');
  receiptScannerLog('UPLOAD_START', { bytes: state.capturedReceiptBlob.size || 0, mime: state.capturedReceiptBlob.type || 'unknown' });

  const stepEl = document.getElementById('scanProcessingStep');
  if (stepEl) stepEl.textContent = 'Отправка изображения на сервер…';

  let timeoutId;
  try {
    const formData = new FormData();
    const source = state.capturedReceiptBlob;
    const sourceName = source instanceof File && source.name ? source.name : 'receipt.jpg';
    formData.append('photo', source, sourceName);

    let url = `/api/group/${state.groupId || 1}/parse/receipt`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    if (stepEl) stepEl.textContent = 'Нейросеть распознаёт позиции и суммы чека…';

    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), 45000);
    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(true),
      body: formData,
      signal: controller.signal
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const error = new Error(errData.error || `HTTP ${res.status}`);
      error.status = res.status;
      error.code = errData.code || '';
      throw error;
    }

    const data = await res.json();
    if (!data.draft || !data.draft.items || data.draft.items.length === 0) {
      throw new Error('Чек не содержит распознанных позиций. Попробуйте сделать фото ближе.');
    }

    state.parsedReceiptDraft = data.draft;
    receiptScannerLog('OCR_DONE', { items: data.draft.items.length, confidence: Number(data.draft.confidence || 0) });
    renderReceiptResult(data.draft);
    setScannerState('result');

    if (tg?.HapticFeedback) {
      try { tg.HapticFeedback.notificationOccurred('success'); } catch (e) {}
    }
  } catch (err) {
    console.error('Failed to parse receipt:', err);
    const isTimeout = err?.name === 'AbortError' || err?.status === 504 || err?.code === 'ocr_timeout';
    const isFormat = err?.status === 415 || err?.code === 'invalid_image';
    const isTooLarge = err?.status === 413;
    const message = isTimeout
      ? 'Распознавание заняло слишком много времени. Попробуйте ещё раз или загрузите более чёткое фото.'
      : isTooLarge
        ? 'Фото слишком большое. Выберите изображение до 15 МБ.'
        : isFormat
          ? 'Этот формат изображения не удалось прочитать. Для HEIC сохраните фото как JPG или выберите другой снимок.'
          : (err.message || 'Произошла ошибка при распознавании. Попробуйте сделать фото ближе и при хорошем освещении.');
    receiptScannerLog('OCR_FAILED', { status: err?.status || 0, code: err?.code || err?.name || 'unknown' });
    showScanError(
      'Не удалось распознать чек',
      message,
      isTimeout ? 'OCR_TIMEOUT' : isFormat ? 'UNSUPPORTED_FORMAT' : isTooLarge ? 'UPLOAD_TOO_LARGE' : 'OCR_FAILED'
    );
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    state.isProcessingReceipt = false;
  }
}

function renderReceiptResult(draft) {
  const merchantInput = document.getElementById('scanResultMerchant');
  const totalInput = document.getElementById('scanResultTotal');
  const badgeEl = document.getElementById('scanResultBadge');
  const warningBanner = document.getElementById('scanResultWarningBanner');
  const warningText = document.getElementById('scanResultWarningText');
  const itemsCountEl = document.getElementById('scanResultItemsCount');

  if (merchantInput) merchantInput.value = draft.merchant || draft.title || 'Чек покупки';
  if (totalInput) totalInput.value = draft.total_amount || 0;
  if (itemsCountEl) itemsCountEl.textContent = draft.items.length;

  if (badgeEl) {
    if (draft.qr_verified) {
      badgeEl.textContent = '✓ ФНС QR проверен';
      badgeEl.className = 'px-2 py-0.5 rounded-lg text-[10px] font-black bg-mint-500/20 text-mint-400 border border-mint-500/30';
    } else {
      badgeEl.textContent = 'OCR AI';
      badgeEl.className = 'px-2 py-0.5 rounded-lg text-[10px] font-black bg-cyan-500/20 text-cyan-400 border border-cyan-500/30';
    }
  }

  if (warningBanner && warningText) {
    if (draft.warning) {
      warningText.textContent = draft.warning;
      warningBanner.classList.remove('hidden');
    } else {
      warningBanner.classList.add('hidden');
    }
  }

  renderParsedItemsList();
  updateReceiptTotals();
}

function renderParsedItemsList() {
  const container = document.getElementById('scanParsedItemsContainer');
  if (!container || !state.parsedReceiptDraft) return;

  const members = state.summary?.members || [
    { id: 1, name: 'Вы' },
    { id: 2, name: 'Кирилл' }
  ];

  container.innerHTML = state.parsedReceiptDraft.items.map((item, idx) => {
    const isAll = !item.participants || item.participants.length === 0 || item.participants.length === members.length;
    const currentUserId = state.currentUser?.id || 1;
    const userInItem = isAll || (item.participants && item.participants.includes(currentUserId));
    const partCount = isAll ? members.length : (item.participants?.length || 1);
    const userPartShare = userInItem ? (item.total_amount / partCount) : 0;

    return `
      <div class="p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] space-y-2.5" data-item-idx="${idx}">
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            <input type="text" class="item-name-input w-full bg-transparent text-xs font-extrabold text-white outline-none focus:border-b border-mint-500/60 transition-all" value="${escapeHtml(item.name)}" data-idx="${idx}">
            <div class="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
              <span>Кол-во:</span>
              <input type="number" step="1" min="1" class="item-qty-input w-12 bg-[#0E1422] rounded px-1.5 py-0.5 text-center text-white outline-none border border-[#222E46]" value="${item.quantity || 1}" data-idx="${idx}">
              <span>×</span>
              <input type="number" step="0.01" min="0" class="item-price-input w-20 bg-[#0E1422] rounded px-1.5 py-0.5 text-center text-white outline-none border border-[#222E46]" value="${item.unit_price || item.total_amount}" data-idx="${idx}">
              <span>₽</span>
            </div>
          </div>
          <div class="text-right flex items-center gap-2">
            <span class="text-sm font-black text-white whitespace-nowrap">${Number(item.total_amount).toLocaleString('ru-RU')} ₽</span>
            <button type="button" class="btn-delete-item text-slate-500 hover:text-rose-400 p-1 transition-colors" data-idx="${idx}" title="Удалить строку">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        </div>

        <!-- Participants Selector -->
        <div class="pt-2 border-t border-[#222E46]">
          <div class="flex items-center justify-between text-[11px] mb-1.5">
            <span class="text-slate-400 font-bold">Кто делит:</span>
            <span class="text-mint-400 font-extrabold">${userInItem ? `Ваша часть: ${Math.round(userPartShare).toLocaleString('ru-RU')} ₽` : 'Вы не делите'}</span>
          </div>
          <div class="flex flex-wrap gap-1.5">
            <button type="button" class="btn-part-all px-2.5 py-1 rounded-lg text-[10px] font-black transition-all ${isAll ? 'bg-mint-500/20 text-mint-400 border border-mint-500/40' : 'bg-[#1E293B] text-slate-400 border border-[#334155]'}" data-idx="${idx}">
              На всех
            </button>
            ${members.map(m => {
              const selected = isAll || (item.participants && item.participants.includes(m.id));
              return `
                <button type="button" class="btn-part-member px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all ${selected ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-[#1E293B]/60 text-slate-500 border border-transparent opacity-60'}" data-idx="${idx}" data-member-id="${m.id}">
                  ${escapeHtml(m.name || m.username || 'Участник')}
                </button>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  }).join('');

  attachItemListeners();
  refreshIcons();
}

function attachItemListeners() {
  const container = document.getElementById('scanParsedItemsContainer');
  if (!container || !state.parsedReceiptDraft) return;

  // Edit name
  container.querySelectorAll('.item-name-input').forEach(input => {
    input.addEventListener('change', (e) => {
      const idx = Number(e.target.getAttribute('data-idx'));
      if (state.parsedReceiptDraft.items[idx]) {
        state.parsedReceiptDraft.items[idx].name = e.target.value;
      }
    });
  });

  // Edit qty & price
  container.querySelectorAll('.item-qty-input, .item-price-input').forEach(input => {
    input.addEventListener('change', (e) => {
      const idx = Number(e.target.getAttribute('data-idx'));
      const row = container.querySelector(`[data-item-idx="${idx}"]`);
      if (!row || !state.parsedReceiptDraft.items[idx]) return;

      const qty = parseFloat(row.querySelector('.item-qty-input').value) || 1;
      const price = parseFloat(row.querySelector('.item-price-input').value) || 0;
      state.parsedReceiptDraft.items[idx].quantity = qty;
      state.parsedReceiptDraft.items[idx].unit_price = price;
      state.parsedReceiptDraft.items[idx].total_amount = Math.round(qty * price * 100) / 100;

      renderParsedItemsList();
      updateReceiptTotals();
    });
  });

  // Delete item
  container.querySelectorAll('.btn-delete-item').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = Number(btn.getAttribute('data-idx'));
      if (state.parsedReceiptDraft.items[idx]) {
        state.parsedReceiptDraft.items.splice(idx, 1);
        renderParsedItemsList();
        updateReceiptTotals();
      }
    });
  });

  // Participant: На всех
  container.querySelectorAll('.btn-part-all').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.getAttribute('data-idx'));
      const members = state.summary?.members || [{ id: 1 }, { id: 2 }];
      if (state.parsedReceiptDraft.items[idx]) {
        state.parsedReceiptDraft.items[idx].participants = members.map(m => m.id);
        renderParsedItemsList();
        updateReceiptTotals();
      }
    });
  });

  // Participant: Member chip toggle
  container.querySelectorAll('.btn-part-member').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.getAttribute('data-idx'));
      const mId = Number(btn.getAttribute('data-member-id'));
      const item = state.parsedReceiptDraft.items[idx];
      const members = state.summary?.members || [{ id: 1 }, { id: 2 }];
      if (!item) return;

      let parts = item.participants ? [...item.participants] : members.map(m => m.id);
      if (parts.includes(mId)) {
        if (parts.length > 1) {
          parts = parts.filter(id => id !== mId);
        }
      } else {
        parts.push(mId);
      }
      item.participants = parts;
      renderParsedItemsList();
      updateReceiptTotals();
    });
  });
}

function updateReceiptTotals() {
  if (!state.parsedReceiptDraft) return;
  const currentUserId = state.currentUser?.id || 1;
  const members = state.summary?.members || [{ id: 1 }, { id: 2 }];

  let userTotalShare = 0;
  let itemsSum = 0;

  state.parsedReceiptDraft.items.forEach(it => {
    itemsSum += (it.total_amount || 0);
    const parts = it.participants && it.participants.length > 0 ? it.participants : members.map(m => m.id);
    if (parts.includes(currentUserId)) {
      userTotalShare += (it.total_amount || 0) / parts.length;
    }
  });

  const totalInput = document.getElementById('scanResultTotal');
  const currentTotal = totalInput ? parseFloat(totalInput.value) || itemsSum : itemsSum;

  const warningBanner = document.getElementById('scanResultWarningBanner');
  const warningText = document.getElementById('scanResultWarningText');
  if (warningBanner && warningText) {
    if (Math.abs(itemsSum - currentTotal) > 1.0) {
      warningText.textContent = `Сумма позиций (${Math.round(itemsSum)} ₽) отличается от итога (${Math.round(currentTotal)} ₽).`;
      warningBanner.classList.remove('hidden');
    } else {
      warningBanner.classList.add('hidden');
    }
  }

  const shareEl = document.getElementById('scanUserShareAmount');
  if (shareEl) {
    shareEl.textContent = `${Math.round(userTotalShare).toLocaleString('ru-RU')} ₽`;
  }
}

async function handleSaveParsedReceipt() {
  if (!state.parsedReceiptDraft || !state.groupId) return;
  const merchantInput = document.getElementById('scanResultMerchant');
  const totalInput = document.getElementById('scanResultTotal');

  const title = (merchantInput ? merchantInput.value : state.parsedReceiptDraft.merchant) || 'Чек покупки';
  const totalAmount = totalInput ? parseFloat(totalInput.value) : state.parsedReceiptDraft.total_amount;
  const items = state.parsedReceiptDraft.items || [];

  if (items.length === 0) {
    showToast('Добавьте хотя бы одну позицию в чек', 'warning');
    return;
  }

  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: title,
        payer_id: state.currentUser?.id || null,
        source_type: 'receipt_photo',
        category: items[0]?.category || '🍞 Продукты',
        currency: 'RUB',
        items: items.map(it => ({
          name: it.name,
          quantity: it.quantity || 1,
          unit_price: it.unit_price || it.total_amount,
          total_amount: it.total_amount,
          category: it.category || '🍞 Продукты',
          participants: it.participants || []
        }))
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    stopReceiptCamera();
    state.capturedReceiptBlob = null;
    state.parsedReceiptDraft = null;

    exitAddExpenseFlow(`Чек «${title}» (${Math.round(totalAmount)} ₽) сохранён!`);
    await fetchSummary();
  } catch (err) {
    console.error('Failed to save itemized receipt expense:', err);
    showToast(`Ошибка сохранения: ${err.message}`, 'error');
  }
}

// ── Screen 5: Реальный голосовой ввод расхода (Whisper AI) ───────────────────
state.voiceState = 'idle'; // 'idle' | 'recording' | 'recorded' | 'processing' | 'error' | 'result'
state.voiceMediaRecorder = null;
state.voiceAudioStream = null;
state.voiceAudioChunks = [];
state.capturedVoiceBlob = null;
state.voiceDurationSeconds = 0;
state.voiceTimerInterval = null;
state.parsedVoiceDraft = null;
let voiceAudioContext = null;
let voiceAnalyser = null;
let voiceAnimFrameId = null;

function getSupportedAudioMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/wav'
  ];
  for (const mime of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return '';
}

function setVoiceState(newState) {
  state.voiceState = newState;
  const states = ['Idle', 'Recording', 'Recorded', 'Processing', 'Error', 'Result'];
  states.forEach(s => {
    const el = document.getElementById(`voiceState${s}`);
    if (el) {
      if (s.toLowerCase() === newState.toLowerCase()) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
  });

  const bottomBar = document.getElementById('voiceBottomBar');
  if (bottomBar) {
    if (newState === 'result') {
      bottomBar.classList.remove('hidden');
    } else {
      bottomBar.classList.add('hidden');
    }
  }
  refreshIcons();
}

function setupVoiceVisualizer(stream) {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    voiceAudioContext = new AudioCtx();
    const source = voiceAudioContext.createMediaStreamSource(stream);
    voiceAnalyser = voiceAudioContext.createAnalyser();
    voiceAnalyser.fftSize = 64;
    source.connect(voiceAnalyser);

    const bufferLength = voiceAnalyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const bars = document.querySelectorAll('#voiceStateRecording .waveform-bar');

    function updateVisualizer() {
      if (state.voiceState !== 'recording') return;
      voiceAnimFrameId = requestAnimationFrame(updateVisualizer);
      voiceAnalyser.getByteFrequencyData(dataArray);

      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const avg = sum / bufferLength;

      bars.forEach((bar, idx) => {
        const val = dataArray[idx % bufferLength] || avg;
        const h = Math.max(12, Math.min(42, Math.round((val / 255) * 44)));
        bar.style.height = `${h}px`;
      });
    }
    updateVisualizer();
  } catch (e) {
    console.warn('Web Audio visualizer setup failed:', e);
  }
}

function cleanupVoiceVisualizer() {
  if (voiceAnimFrameId) {
    cancelAnimationFrame(voiceAnimFrameId);
    voiceAnimFrameId = null;
  }
  if (voiceAnalyser) {
    try { voiceAnalyser.disconnect(); } catch (e) {}
    voiceAnalyser = null;
  }
  if (voiceAudioContext) {
    try { voiceAudioContext.close(); } catch (e) {}
    voiceAudioContext = null;
  }
}

function stopVoiceMicrophone() {
  if (state.voiceTimerInterval) {
    clearInterval(state.voiceTimerInterval);
    state.voiceTimerInterval = null;
  }

  if (state.voiceMediaRecorder && state.voiceMediaRecorder.state !== 'inactive') {
    try {
      state.voiceMediaRecorder.stop();
    } catch (e) {}
  }

  if (state.voiceAudioStream) {
    state.voiceAudioStream.getTracks().forEach(track => {
      try { track.stop(); } catch (e) {}
    });
    state.voiceAudioStream = null;
  }

  cleanupVoiceVisualizer();

  const player = document.getElementById('voiceAudioPlayer');
  if (player) {
    try {
      player.pause();
      player.removeAttribute('src');
      player.load();
    } catch (e) {}
  }
}

function resetVoiceRecording() {
  stopVoiceMicrophone();
  state.capturedVoiceBlob = null;
  state.voiceAudioChunks = [];
  state.parsedVoiceDraft = null;
  state.voiceDurationSeconds = 0;
  setVoiceState('idle');
}

function formatRecordTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

async function startVoiceRecording() {
  if (!window.isSecureContext) {
    const errEl = document.getElementById('voiceErrorMessage');
    if (errEl) errEl.textContent = 'Для записи голоса требуется защищённое HTTPS-соединение.';
    setVoiceState('error');
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const errEl = document.getElementById('voiceErrorMessage');
    if (errEl) errEl.textContent = 'Ваш браузер или клиент Telegram не поддерживает запись звука.';
    setVoiceState('error');
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.voiceAudioStream = stream;
    state.voiceAudioChunks = [];
    state.voiceDurationSeconds = 0;

    const mime = getSupportedAudioMimeType();
    const options = mime ? { mimeType: mime } : undefined;
    state.voiceMediaRecorder = new MediaRecorder(stream, options);

    state.voiceMediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        state.voiceAudioChunks.push(e.data);
      }
    };

    state.voiceMediaRecorder.onstop = () => {
      handleVoiceRecordingFinished();
    };

    // Запуск записи с порциями каждые 250мс
    state.voiceMediaRecorder.start(250);

    // Запуск Web Audio анализатора
    setupVoiceVisualizer(stream);

    // Настройка таймера
    const timerEl = document.getElementById('voiceRecordingTimer');
    if (timerEl) timerEl.textContent = '00:00';

    if (state.voiceTimerInterval) clearInterval(state.voiceTimerInterval);
    state.voiceTimerInterval = setInterval(() => {
      state.voiceDurationSeconds++;
      if (timerEl) timerEl.textContent = formatRecordTime(state.voiceDurationSeconds);
      if (state.voiceDurationSeconds >= 60) {
        // Лимит 60 секунд авто-стоп
        stopVoiceRecording();
        showToast('Достигнут лимит записи 60 секунд', 'info');
      }
    }, 1000);

    // Тактильный отклик
    if (window.Telegram?.WebApp?.HapticFeedback) {
      try { window.Telegram.WebApp.HapticFeedback.impactOccurred('medium'); } catch (e) {}
    } else if (navigator.vibrate) {
      navigator.vibrate(50);
    }

    setVoiceState('recording');
  } catch (err) {
    console.error('Microphone permission or start error:', err);
    let msg = 'Не удалось получить доступ к микрофону.';
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      msg = 'Telegram не получил доступ к микрофону. Разрешите микрофон в настройках устройства или браузера и попробуйте снова.';
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      msg = 'Микрофон на вашем устройстве не обнаружен.';
    } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
      msg = 'Микрофон занят другим приложением устройства. Закройте его и повторите попытку.';
    }
    const errEl = document.getElementById('voiceErrorMessage');
    if (errEl) errEl.textContent = msg;
    setVoiceState('error');
  }
}

function stopVoiceRecording() {
  if (state.voiceTimerInterval) {
    clearInterval(state.voiceTimerInterval);
    state.voiceTimerInterval = null;
  }

  if (state.voiceMediaRecorder && state.voiceMediaRecorder.state !== 'inactive') {
    state.voiceMediaRecorder.stop();
  }

  if (state.voiceAudioStream) {
    state.voiceAudioStream.getTracks().forEach(t => {
      try { t.stop(); } catch (e) {}
    });
    state.voiceAudioStream = null;
  }

  cleanupVoiceVisualizer();

  if (window.Telegram?.WebApp?.HapticFeedback) {
    try { window.Telegram.WebApp.HapticFeedback.notificationOccurred('success'); } catch (e) {}
  } else if (navigator.vibrate) {
    navigator.vibrate(50);
  }
}

function handleVoiceRecordingFinished() {
  const mime = state.voiceMediaRecorder?.mimeType || 'audio/webm';
  const blob = new Blob(state.voiceAudioChunks, { type: mime });
  state.capturedVoiceBlob = blob;

  const durationTitle = document.getElementById('voiceRecordedDurationTitle');
  if (durationTitle) {
    durationTitle.textContent = `Запись завершена · ${formatRecordTime(state.voiceDurationSeconds)}`;
  }

  const player = document.getElementById('voiceAudioPlayer');
  if (player && blob.size > 0) {
    const audioUrl = URL.createObjectURL(blob);
    player.src = audioUrl;
  }

  setVoiceState('recorded');
}

async function uploadAndProcessVoice() {
  if (!state.capturedVoiceBlob || state.capturedVoiceBlob.size === 0) {
    showToast('Сначала запишите голос', 'warning');
    return;
  }

  if (!state.groupId) {
    showToast('Комната не выбрана', 'error');
    return;
  }

  setVoiceState('processing');
  const stepEl = document.getElementById('voiceProcessingStep');
  if (stepEl) stepEl.textContent = '1/3. Загружаем аудиозапись...';

  try {
    const mime = state.capturedVoiceBlob.type || '';
    let ext = '.webm';
    if (mime.includes('mp4')) ext = '.mp4';
    else if (mime.includes('ogg')) ext = '.ogg';
    else if (mime.includes('wav')) ext = '.wav';
    else if (mime.includes('mpeg') || mime.includes('mp3')) ext = '.mp3';

    const formData = new FormData();
    formData.append('audio', state.capturedVoiceBlob, `recording${ext}`);

    let url = `/api/group/${state.groupId}/parse/voice`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    if (stepEl) stepEl.textContent = '2/3. Whisper расшифровывает русскую речь...';

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(true),
      body: formData
    });

    if (stepEl) stepEl.textContent = '3/3. ИИ распределяет суммы и участников...';

    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error) {
      const msg = data.message || data.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }

    const draft = data.draft;
    if (!draft || !draft.transcription) {
      throw new Error('Не удалось получить расшифровку речи.');
    }

    state.parsedVoiceDraft = draft;
    renderVoiceResult();
    setVoiceState('result');

    if (draft.warning) {
      showToast(draft.warning, 'info');
    } else {
      showToast('Голос успешно расшифрован!', 'success');
    }
  } catch (err) {
    console.error('Error processing voice expense:', err);
    const errEl = document.getElementById('voiceErrorMessage');
    if (errEl) errEl.textContent = err.message || 'Ошибка распознавания речи.';
    setVoiceState('error');
  }
}

function renderVoiceResult() {
  if (!state.parsedVoiceDraft) return;
  const draft = state.parsedVoiceDraft;

  const quoteEl = document.getElementById('voiceTranscribedQuote');
  if (quoteEl) {
    quoteEl.textContent = `«${draft.transcription || ''}»`;
  }

  const durationBadge = document.getElementById('voiceResultDurationBadge');
  if (durationBadge) {
    durationBadge.textContent = formatRecordTime(state.voiceDurationSeconds);
  }

  const warningCard = document.getElementById('voiceWarningCard');
  const warningText = document.getElementById('voiceWarningText');
  if (warningCard && warningText) {
    if (draft.warning) {
      warningText.textContent = draft.warning;
      warningCard.classList.remove('hidden');
    } else {
      warningCard.classList.add('hidden');
    }
  }

  const titleInput = document.getElementById('voiceResultTitle');
  if (titleInput) {
    titleInput.value = draft.title || 'Голосовой расход';
  }

  const totalInput = document.getElementById('voiceResultTotal');
  if (totalInput) {
    totalInput.value = Math.round(draft.total_amount || 0);
  }

  renderVoiceItemsList();
  updateVoiceTotals();
}

function renderVoiceItemsList() {
  const container = document.getElementById('voiceExtractedItemsContainer');
  const countBadge = document.getElementById('voiceItemsCountBadge');
  if (!container || !state.parsedVoiceDraft) return;

  const items = state.parsedVoiceDraft.items || [];
  if (countBadge) countBadge.textContent = `${items.length} ${items.length === 1 ? 'позиция' : 'позиций'}`;

  const members = state.summary?.members || [
    { id: 1, display_name: 'Вы' },
    { id: 2, display_name: 'Кирилл' },
    { id: 3, display_name: 'Денис' }
  ];

  if (items.length === 0) {
    container.innerHTML = `
      <div class="p-4 rounded-2xl bg-[#0E1422] border border-[#222E46] text-center text-xs text-slate-400">
        Позиции не выделены. Добавьте позицию кнопкой ниже.
      </div>
    `;
    return;
  }

  let html = '';
  items.forEach((item, idx) => {
    const name = escapeHtml(item.name || `Позиция ${idx + 1}`);
    const price = Math.round(item.unit_price || item.total_amount || 0);
    const qty = item.quantity || 1;
    const total = Math.round(item.total_amount || price * qty);
    const itemParts = Array.isArray(item.participants) && item.participants.length > 0
      ? item.participants
      : members.map(m => m.id);

    const isAll = itemParts.length === members.length;
    const partSummary = isAll ? 'На всех' : `${itemParts.length} чел.`;

    html += `
      <div class="p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] space-y-2.5" data-voice-item-index="${idx}">
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            <input type="text" class="voice-item-name-input w-full bg-transparent text-xs font-extrabold text-white border-b border-transparent focus:border-amber-400 focus:outline-none" value="${name}" data-idx="${idx}">
            <div class="flex items-center gap-2 mt-1 text-[11px] text-slate-400">
              <span>${qty} шт. × </span>
              <input type="number" class="voice-item-price-input w-16 bg-[#0E1422] rounded px-1.5 py-0.5 text-right text-white font-mono border border-[#222E46] focus:border-amber-400 focus:outline-none" value="${price}" data-idx="${idx}">
              <span>₽ = </span>
              <span class="font-bold text-white">${total} ₽</span>
            </div>
          </div>
          <button type="button" class="btn-delete-voice-item p-1.5 text-slate-500 hover:text-red-400 transition-all active:scale-90" data-idx="${idx}" title="Удалить позицию">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>

        <!-- Participants Chips -->
        <div class="pt-1 border-t border-[#222E46]/60">
          <div class="flex items-center justify-between text-[11px] text-slate-400 mb-1.5">
            <span>Кто делит (${partSummary}):</span>
            <button type="button" class="btn-voice-toggle-all text-amber-400 hover:text-amber-300 font-bold" data-idx="${idx}">
              ${isAll ? 'Выбрать' : 'На всех'}
            </button>
          </div>
          <div class="flex flex-wrap gap-1.5">
    `;

    members.forEach(m => {
      const active = itemParts.includes(m.id);
      const mName = escapeHtml(m.display_name || m.username || `User #${m.id}`);
      html += `
        <button type="button" class="btn-voice-member-chip px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
          active
            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
            : 'bg-[#0E1422] text-slate-400 border border-[#222E46] opacity-60'
        }" data-item-idx="${idx}" data-member-id="${m.id}">
          ${mName}
        </button>
      `;
    });

    html += `
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  attachVoiceItemListeners();
  refreshIcons();
}

function attachVoiceItemListeners() {
  if (!state.parsedVoiceDraft) return;
  const members = state.summary?.members || [{ id: 1 }, { id: 2 }];

  // Name editing
  document.querySelectorAll('.voice-item-name-input').forEach(input => {
    input.addEventListener('change', (e) => {
      const idx = parseInt(e.target.dataset.idx);
      if (state.parsedVoiceDraft?.items[idx]) {
        state.parsedVoiceDraft.items[idx].name = e.target.value.trim() || 'Позиция';
      }
    });
  });

  // Price editing
  document.querySelectorAll('.voice-item-price-input').forEach(input => {
    input.addEventListener('input', (e) => {
      const idx = parseInt(e.target.dataset.idx);
      const p = parseFloat(e.target.value) || 0;
      if (state.parsedVoiceDraft?.items[idx]) {
        const item = state.parsedVoiceDraft.items[idx];
        item.unit_price = p;
        item.total_amount = p * (item.quantity || 1);
        updateVoiceTotals();
      }
    });
  });

  // Delete item
  document.querySelectorAll('.btn-delete-voice-item').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(btn.dataset.idx);
      if (state.parsedVoiceDraft?.items) {
        state.parsedVoiceDraft.items.splice(idx, 1);
        renderVoiceItemsList();
        updateVoiceTotals();
      }
    });
  });

  // Toggle All
  document.querySelectorAll('.btn-voice-toggle-all').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(btn.dataset.idx);
      const item = state.parsedVoiceDraft?.items[idx];
      if (!item) return;
      const allIds = members.map(m => m.id);
      const current = item.participants || [];
      if (current.length === allIds.length) {
        item.participants = [state.currentUser?.id || allIds[0]];
      } else {
        item.participants = [...allIds];
      }
      renderVoiceItemsList();
      updateVoiceTotals();
    });
  });

  // Member chip toggle
  document.querySelectorAll('.btn-voice-member-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const itemIdx = parseInt(btn.dataset.itemIdx);
      const mId = parseInt(btn.dataset.memberId);
      const item = state.parsedVoiceDraft?.items[itemIdx];
      if (!item) return;

      let parts = item.participants ? [...item.participants] : members.map(m => m.id);
      if (parts.includes(mId)) {
        if (parts.length > 1) {
          parts = parts.filter(id => id !== mId);
        }
      } else {
        parts.push(mId);
      }
      item.participants = parts;
      renderVoiceItemsList();
      updateVoiceTotals();
    });
  });
}

function updateVoiceTotals() {
  if (!state.parsedVoiceDraft) return;
  const currentUserId = state.currentUser?.id || 1;
  const members = state.summary?.members || [{ id: 1 }, { id: 2 }];

  let userTotalShare = 0;
  let itemsSum = 0;

  (state.parsedVoiceDraft.items || []).forEach(it => {
    const tot = (it.total_amount || 0);
    itemsSum += tot;
    const parts = it.participants && it.participants.length > 0 ? it.participants : members.map(m => m.id);
    if (parts.includes(currentUserId)) {
      userTotalShare += tot / parts.length;
    }
  });

  const totalInput = document.getElementById('voiceResultTotal');
  if (totalInput && (!totalInput.value || totalInput.value == 0)) {
    totalInput.value = Math.round(itemsSum);
  }
  const currentTotal = totalInput ? parseFloat(totalInput.value) || itemsSum : itemsSum;

  const shareEl = document.getElementById('voiceUserShareAmount');
  if (shareEl) {
    shareEl.textContent = `${Math.round(userTotalShare).toLocaleString('ru-RU')} ₽`;
  }

  const submitText = document.getElementById('btnSubmitVoiceText');
  if (submitText) {
    submitText.textContent = `Внести расход ${Math.round(currentTotal).toLocaleString('ru-RU')} ₽ в комнату`;
  }
}

async function handleSaveVoiceExpense() {
  if (!state.parsedVoiceDraft || !state.groupId) return;
  const titleInput = document.getElementById('voiceResultTitle');
  const totalInput = document.getElementById('voiceResultTotal');

  const title = (titleInput ? titleInput.value.trim() : state.parsedVoiceDraft.title) || 'Голосовой расход';
  const totalAmount = totalInput ? parseFloat(totalInput.value) : state.parsedVoiceDraft.total_amount;
  const items = state.parsedVoiceDraft.items || [];

  if (items.length === 0) {
    showToast('Добавьте хотя бы одну позицию расхода', 'warning');
    return;
  }

  const submitBtn = document.getElementById('btnSubmitVoiceExpense');
  if (submitBtn) {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'pointer-events-none');
  }

  try {
    let url = `/api/group/${state.groupId}/expense/itemized`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({
        title: title,
        payer_id: state.currentUser?.id || null,
        source_type: 'voice',
        category: items[0]?.category || '🍞 Продукты',
        currency: 'RUB',
        items: items.map(it => ({
          name: it.name,
          quantity: it.quantity || 1,
          unit_price: it.unit_price || it.total_amount,
          total_amount: it.total_amount,
          category: it.category || '🍞 Продукты',
          participants: it.participants || []
        }))
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    stopVoiceMicrophone();
    state.capturedVoiceBlob = null;
    state.parsedVoiceDraft = null;

    exitAddExpenseFlow(`Голосовой расход «${title}» (${Math.round(totalAmount)} ₽) сохранён!`);
    await fetchSummary();
  } catch (err) {
    console.error('Failed to save itemized voice expense:', err);
    showToast(`Ошибка сохранения: ${err.message}`, 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove('opacity-50', 'pointer-events-none');
    }
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

  const btnSubmit = document.getElementById('btnSubmitExpense');
  if (btnSubmit) {
    if (btnSubmit.disabled) return;
    btnSubmit.disabled = true;
    btnSubmit.classList.add('opacity-50', 'pointer-events-none');
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
        split_with: splitWith,
        client_request_id: crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`
      })
    });

    if (res.status === 403) {
      showToast('Доступ запрещён: вы не участник этой комнаты', 'error');
      return;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    exitAddExpenseFlow(data.message || 'Расход успешно добавлен!');

    if (amountInput) amountInput.value = '';
    if (titleInput) titleInput.value = '';

    await fetchSummary();
  } catch (e) {
    console.error('Failed to submit expense:', e);
    showToast('Ошибка при добавлении расхода', 'error');
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.classList.remove('opacity-50', 'pointer-events-none');
    }
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
  if (state.isConfirmingSettlement) return;
  const amount = state.selectedDebt.amount;
  const requestId = state.settlementRequestId || (window.crypto?.randomUUID?.() || `settlement-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  state.settlementRequestId = requestId;
  state.isConfirmingSettlement = true;

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
        amount: amount,
        client_request_id: requestId
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
  } finally {
    state.isConfirmingSettlement = false;
    state.settlementRequestId = null;
  }
}

function openTransactionSheet(txId) {
  const txList = state.summary?.expenses || [];
  const tx = txList.find(t => t.id === txId);
  if (!tx) return;

  state.selectedTx = tx;
  const color = getCategoryColor(tx.category);
  const icon = getMerchantIcon(tx.merchant || tx.title || tx.description, tx.category);

  const iconEl = document.getElementById('txModalIcon');
  if (iconEl) {
    iconEl.innerHTML = icon;
    iconEl.style.backgroundColor = `${color}20`;
    iconEl.style.color = color;
  }

  const amtEl = document.getElementById('txModalAmount');
  if (amtEl) amtEl.textContent = formatCurrency(tx.amount);

  const descEl = document.getElementById('txModalNote');
  if (descEl) descEl.textContent = getTransactionDisplayTitle(tx);

  const catEl = document.getElementById('txModalCategory');
  if (catEl) catEl.textContent = getCategoryLabel(tx.category);

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

function ensureWelcomeScreen() {
  let screen = document.getElementById('welcomeScreen');
  if (screen) return screen;
  screen = document.createElement('section');
  screen.id = 'welcomeScreen';
  screen.className = 'absolute inset-0 z-40 flex min-h-[100dvh] flex-col items-center justify-start overflow-y-auto overflow-x-hidden bg-[#06131A] px-5 pb-[calc(40px+env(safe-area-inset-bottom))] pt-[max(32px,env(safe-area-inset-top))] text-center';
  screen.style.backgroundImage = 'radial-gradient(circle at 50% 36%, rgba(0,229,153,.10), transparent 34%), radial-gradient(circle at 10% 90%, rgba(0,174,160,.12), transparent 28%), linear-gradient(145deg, #06131A 0%, #071720 48%, #081924 100%)';
  screen.innerHTML = `
    <div aria-hidden="true" class="pointer-events-none absolute -left-16 top-16 rotate-[-12deg] rounded-3xl border border-teal-300/20 bg-teal-300/[.06] p-4 opacity-70 shadow-[0_0_35px_rgba(0,229,153,.12)]"><i data-lucide="bar-chart-3" class="h-24 w-24 text-teal-300/50"></i></div>
    <div aria-hidden="true" class="pointer-events-none absolute -right-8 top-16 rounded-full border border-emerald-300/20 bg-emerald-300/[.05] p-3 opacity-80"><i data-lucide="circle-check" class="h-20 w-20 text-emerald-300/70"></i></div>
    <div aria-hidden="true" class="pointer-events-none absolute -right-8 top-[30%] rotate-[14deg] rounded-3xl border border-cyan-200/15 bg-cyan-200/[.05] px-6 py-4 text-5xl font-black text-cyan-200/25">₽</div>
    <div aria-hidden="true" class="pointer-events-none absolute -left-10 bottom-10 rotate-[-12deg] rounded-3xl border border-teal-200/15 bg-teal-200/[.05] p-5 text-left opacity-70"><p class="text-xs font-bold text-teal-100/50">Расходы</p><p class="mt-2 text-2xl font-black text-teal-100/45">− 2 450 ₽</p><div class="mt-3 h-1.5 w-32 rounded-full bg-teal-200/15"></div><div class="mt-2 h-1.5 w-24 rounded-full bg-teal-200/10"></div></div>
    <div aria-hidden="true" class="pointer-events-none absolute -right-4 bottom-20 h-36 w-36 rounded-full border border-emerald-300/20 bg-emerald-300/[.05] opacity-80"><div class="absolute inset-4 rounded-full border border-emerald-300/15"></div><div class="absolute right-0 top-0 h-1/2 w-1/2 rounded-tr-full bg-emerald-300/55"></div></div>
    <div aria-hidden="true" class="pointer-events-none absolute left-[22%] top-[24%] h-2.5 w-2.5 rounded-full bg-[#00E599] shadow-[0_0_14px_#00E599]"></div><div aria-hidden="true" class="pointer-events-none absolute right-[22%] bottom-[32%] h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_#22D3EE]"></div>
    <div class="relative z-10 flex min-h-[calc(100dvh-72px)] w-full max-w-[600px] flex-col items-center justify-center py-12">
      <div class="mx-auto mb-6 flex h-[78px] w-[78px] items-center justify-center rounded-[24px] border border-[#00E599]/30 bg-[#062A2B]/80 text-[#00E599] shadow-[0_0_40px_rgba(0,229,153,.24)]"><i data-lucide="sparkles" class="h-10 w-10"></i></div>
      <h1 class="text-[clamp(38px,11vw,52px)] font-extrabold tracking-[-0.05em] text-white">Sber<span class="text-[#00E6A2]">Wise</span></h1>
      <p class="mt-3 text-base font-semibold text-[#8D9AAA]">ваш умный помощник по бюджету</p>
      <div id="welcomeActions" class="mt-12 w-full max-w-[600px] space-y-3 px-3">
        <button id="welcomeCreate" type="button" class="flex h-16 w-full items-center justify-center gap-3 rounded-[22px] bg-gradient-to-r from-[#00D9A0] to-[#00F0A8] text-base font-black text-[#06281E] shadow-[0_0_28px_rgba(0,229,153,.22)] transition active:brightness-110"><i data-lucide="plus" class="h-6 w-6"></i>Создать новую комнату</button>
        <button id="welcomeContinue" type="button" class="flex h-16 w-full items-center justify-center gap-3 rounded-[22px] border border-[#526985]/40 bg-[#111C2F]/85 text-base font-extrabold text-white shadow-[0_8px_24px_rgba(0,0,0,.16)] transition active:border-[#00E599]/50"><i data-lucide="arrow-right" class="h-6 w-6 text-[#00E599]"></i>Продолжить использование</button>
      </div>
      <div id="welcomeRooms" class="mt-8 hidden w-full text-left"></div>
    </div>`;
  document.getElementById('appShell')?.appendChild(screen);
  screen.querySelector('#welcomeCreate').addEventListener('click', openCreateRoomFromWelcome);
  screen.querySelector('#welcomeContinue').addEventListener('click', () => showAvailableRooms());
  refreshIcons();
  return screen;
}

async function openRoomSetupScreen() {
  const screen = ensureWelcomeScreen();
  const content = screen.querySelector('.relative.z-10');
  if (!content) return;
  screen.style.paddingTop = 'max(12px, env(safe-area-inset-top))';
  content.classList.remove('justify-center', 'py-12');
  content.classList.add('justify-start', 'pt-[calc(env(safe-area-inset-top)+12px)]', 'pb-12');
  content.innerHTML = `<button id="setupBack" type="button" aria-label="Назад" class="absolute left-0 top-0 flex h-10 w-10 items-center justify-center rounded-2xl border border-teal-300/25 bg-[#10242B]/85 text-[#D8FFF4] shadow-[0_8px_22px_rgba(0,0,0,.22)] transition hover:border-[#00E599]/60 hover:text-[#00E599] active:scale-95"><i data-lucide="arrow-left" class="h-5 w-5"></i></button><h1 class="pt-2 text-2xl font-extrabold text-white">Создание комнаты</h1><p class="mt-3 text-sm leading-relaxed text-slate-400">Подключите SberWise к Telegram-группе, чтобы вести общий бюджет вместе.</p><div id="manualSetup" class="mt-6 text-left"><div class="rounded-2xl border border-amber-400/40 bg-[#171A21] p-4"><p class="text-sm font-extrabold text-amber-300">⚠ Автоматическое подключение на данный момент в разработке</p></div><div class="mt-4 rounded-2xl border border-[#273653] bg-[#151D2E] p-4"><p class="text-sm font-extrabold text-white">Как подключить SberWise вручную</p><ol class="mt-3 space-y-2.5 text-xs leading-relaxed text-slate-300"><li><b class="mr-2 text-[#00E599]">1.</b>Создайте новый групповой чат в Telegram.</li><li><b class="mr-2 text-[#00E599]">2.</b>Добавьте в группу друзей, с которыми хотите вести общий бюджет.</li><li><b class="mr-2 text-[#00E599]">3.</b>Добавьте в эту группу бота SberWise.</li><li><b class="mr-2 text-[#00E599]">4.</b>Назначьте SberWise администратором группы.</li><li><b class="mr-2 text-[#00E599]">5.</b>Разрешите боту необходимые права для работы в чате.</li><li><b class="mr-2 text-[#00E599]">6.</b>После этого можно пользоваться ботом прямо в группе.</li></ol><div class="mt-4 border-t border-[#273653] pt-4"><p class="text-xs font-bold text-slate-400">Все команды бота:</p><div class="mt-2 rounded-xl border border-[#00E599]/30 bg-[#0E1422] px-3 py-2 font-mono text-sm font-bold text-[#00E599]">/help</div><p class="mt-2 text-[11px] text-slate-500">Отправьте эту команду в Telegram-группе.</p></div><p class="mt-4 text-[11px] text-slate-500">Уже добавили бота? Перейдите в группу и используйте /help.</p></div></div>`;
  const setupBack = content.querySelector('#setupBack');
  const setupTitle = content.querySelector('h1');
  if (setupBack && setupTitle) {
    const header = document.createElement('div');
    header.className = 'room-create-header grid w-full grid-cols-[44px_minmax(0,1fr)_44px] items-center gap-3';
    setupBack.className = 'flex h-11 w-11 items-center justify-center rounded-2xl border border-teal-300/25 bg-[#10242B]/80 text-[#D8FFF4] shadow-[0_6px_18px_rgba(0,0,0,.18)] transition hover:border-[#00E599]/60 hover:text-[#00E599] active:scale-95';
    setupTitle.className = 'min-w-0 text-center text-2xl font-extrabold text-white';
    const spacer = document.createElement('div');
    spacer.className = 'h-11 w-11';
    content.insertBefore(header, setupTitle);
    header.append(setupBack, setupTitle, spacer);
  }
  screen.classList.remove('hidden');
  document.getElementById('mainContent')?.classList.add('hidden'); document.getElementById('bottomNav')?.classList.add('hidden');
  content.querySelector('#setupBack').onclick = () => { screen.remove(); ensureWelcomeScreen(); };
  refreshIcons();
}

function openCreateRoomFromWelcome() {
  openCreateRoomScreen('welcome');
}

async function showAvailableRooms() {
  const screen = ensureWelcomeScreen();
  const actions = screen.querySelector('#welcomeActions');
  const roomsBox = screen.querySelector('#welcomeRooms');
  const welcomeContent = screen.querySelector('.relative.z-10');
  if (welcomeContent) {
    screen.style.paddingTop = 'max(12px, env(safe-area-inset-top))';
    welcomeContent.classList.remove('justify-center', 'py-12');
    welcomeContent.classList.add('justify-start', 'pt-[calc(env(safe-area-inset-top)+12px)]', 'pb-12');
  }
  if (actions) actions.classList.add('hidden');
  if (!roomsBox) return;
  if (welcomeContent && !welcomeContent.querySelector('#continueBackHeader')) {
    const header = document.createElement('div');
    header.id = 'continueBackHeader';
    header.className = 'mb-4 grid w-full grid-cols-[44px_minmax(0,1fr)_44px] items-center gap-3';
    header.innerHTML = '<button id="continueBack" type="button" aria-label="Назад" class="flex h-11 w-11 items-center justify-center rounded-2xl border border-teal-300/25 bg-[#10242B]/80 text-[#D8FFF4] shadow-[0_6px_18px_rgba(0,0,0,.18)] transition hover:border-[#00E599]/60 hover:text-[#00E599] active:scale-95"><i data-lucide="arrow-left" class="h-5 w-5"></i></button><h2 class="min-w-0 text-center text-lg font-extrabold text-white">Продолжить использование</h2><div class="h-11 w-11"></div>';
    welcomeContent.insertBefore(header, welcomeContent.firstElementChild);
    header.querySelector('#continueBack').addEventListener('click', () => {
      actions?.classList.remove('hidden');
      roomsBox.classList.add('hidden');
      header.remove();
      screen.style.paddingTop = '';
      welcomeContent.classList.remove('justify-start', 'pt-[calc(env(safe-area-inset-top)+12px)]', 'pb-12');
      welcomeContent.classList.add('justify-center', 'py-12');
    });
    refreshIcons();
  }
  roomsBox.classList.remove('hidden');
  const rooms = state.availableGroups || [];
  if (!rooms.length) {
    roomsBox.innerHTML = `<div class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-5 text-center"><p class="text-sm font-extrabold text-white">У вас пока нет комнат</p><p class="mt-2 text-xs text-slate-400">Создайте комнату и подключите её к группе Telegram.</p><button id="welcomeCreateFirst" class="mt-5 h-12 w-full rounded-xl bg-[#00D29D] text-sm font-black text-[#06281E]">Создать первую комнату</button></div>`;
    roomsBox.querySelector('#welcomeCreateFirst').addEventListener('click', () => openCreateRoomScreen('welcome'));
    return;
  }
  if (rooms.length === 1) { selectWelcomeRoom(rooms[0].id); return; }
  roomsBox.innerHTML = `<p class="mb-3 text-sm font-extrabold text-white">Ваши комнаты</p>` + rooms.map(room => `<button type="button" data-room-id="${Number(room.id)}" class="mb-2 flex w-full items-center justify-between rounded-2xl border border-[#222E46] bg-[#151D2E] p-4 text-left"><span><b class="block text-sm text-white">${escapeHtml(room.name || 'Комната')}</b><small class="text-xs text-slate-400">${Number(room.members_count || 0)} участников</small></span><i data-lucide="chevron-right" class="h-4 w-4 text-[#00E599]"></i></button>`).join('');
  roomsBox.querySelectorAll('[data-room-id]').forEach(btn => btn.addEventListener('click', () => selectWelcomeRoom(Number(btn.dataset.roomId))));
  refreshIcons();
}

async function selectWelcomeRoom(roomId) {
  const screen = document.getElementById('welcomeScreen');
  state.groupId = Number(roomId);
  try { localStorage.setItem('sberwise_last_room_id', String(roomId)); } catch (e) {}
  screen?.classList.add('hidden');
  const mainContent = document.getElementById('mainContent');
  const bottomNav = document.getElementById('bottomNav');
  mainContent?.classList.remove('hidden');
  bottomNav?.classList.remove('hidden');
  mainContent?.removeAttribute('hidden');
  bottomNav?.removeAttribute('hidden');
  if (mainContent) mainContent.style.display = '';
  if (bottomNav) bottomNav.style.display = '';
  await fetchSummary();
}

async function inviteDebtMember() {
  if (!state.groupId) return;
  await requestRoomInviteDelivery(state.groupId);
}

async function requestRoomInviteDelivery(roomId) {
  try {
    if (typeof tg?.shareMessage !== 'function') {
      throw new Error('Обновите Telegram, чтобы отправлять приглашения из Mini App');
    }
    const response = await fetch(appendTgUserId(`/api/rooms/${roomId}/prepared-invites`), { method: 'POST', headers: getRequestHeaders() });
    const data = await response.json();
    if (!response.ok || !data.prepared_message_id) throw new Error(data.error || 'Не удалось подготовить приглашение');
    tg.shareMessage(data.prepared_message_id, (sent) => {
      if (sent) showToast('Приглашение отправлено', 'success');
    });
  } catch (err) {
    console.error('Invite share failed:', err);
    showToast(err.message || 'Не удалось открыть приглашение', 'error');
  }
}

async function addFromTelegram() {
  if (!state.groupId) return;
  if (state.isTelegramMemberPickerPending) return;
  const button = document.getElementById('btnAddFromTelegram');
  state.isTelegramMemberPickerPending = true;
  if (button) {
    button.disabled = true;
    button.classList.add('opacity-70', 'cursor-wait');
    button.textContent = 'Ожидаем выбор в Telegram…';
  }
  try {
    const res = await fetch(appendTgUserId(`/api/group/${state.groupId}/member-import-requests`), { method: 'POST', headers: getRequestHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Не удалось открыть выбор Telegram');
    state.telegramMemberPickerRequestId = data.request_id;
    watchTelegramMemberPicker(data.request_id);
    showToast(data.already_pending ? 'Выбор участников уже ожидает подтверждения в Telegram' : 'Откройте Telegram и выберите участников', 'success');
  } catch (err) {
    showToast(err.message || 'Не удалось открыть выбор Telegram', 'error');
    state.isTelegramMemberPickerPending = false;
    if (button) {
      button.disabled = false;
      button.classList.remove('opacity-70', 'cursor-wait');
      button.textContent = '＋ Добавить из Telegram';
    }
  }
}

function resetTelegramMemberPicker(message = '') {
  if (state.telegramMemberPickerPoll) clearInterval(state.telegramMemberPickerPoll);
  state.telegramMemberPickerPoll = null;
  state.telegramMemberPickerRequestId = null;
  state.isTelegramMemberPickerPending = false;
  const button = document.getElementById('btnAddFromTelegram');
  if (button) {
    button.disabled = false;
    button.classList.remove('opacity-70', 'cursor-wait');
    button.textContent = '＋ Добавить из Telegram';
  }
  if (message) showToast(message, 'success');
}

function watchTelegramMemberPicker(requestId) {
  if (!requestId || state.telegramMemberPickerPoll) return;
  const poll = async () => {
    try {
      const res = await fetch(appendTgUserId(`/api/group/${state.groupId}/member-import-requests/${requestId}`), { headers: getRequestHeaders() });
      const data = await res.json();
      if (!res.ok || data.status === 'pending') return;
      if (data.status === 'completed') {
        await fetchSummary();
        openCreateDebtSheet();
        resetTelegramMemberPicker('Участники добавлены в комнату');
      } else {
        resetTelegramMemberPicker();
      }
    } catch (e) { /* Keep the visible pending state; it will recover on the next poll. */ }
  };
  state.telegramMemberPickerPoll = setInterval(poll, 3000);
  setTimeout(() => {
    if (state.telegramMemberPickerRequestId === requestId) resetTelegramMemberPicker();
  }, 10 * 60 * 1000);
}

function setCreateDebtDirection(dir) {
  state.createDebtDirection = dir;
  const btnOwed = document.getElementById('debtDirOwedToMe');
  const btnIOwe = document.getElementById('debtDirIOwe');
  const label = document.getElementById('debtCounterpartyLabel');

  if (dir === 'owed_to_me') {
    if (btnOwed) btnOwed.className = 'debt-dir-btn active py-2.5 px-3 rounded-xl border-2 border-[#00D29D] bg-[#00D29D]/20 text-xs font-extrabold text-[#00E599] flex items-center justify-center gap-1.5 transition-all shadow-sm';
    if (btnIOwe) btnIOwe.className = 'debt-dir-btn py-2.5 px-3 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-300 flex items-center justify-center gap-1.5 transition-all';
    if (label) label.textContent = 'Кто должен вам?';
  } else {
    if (btnIOwe) btnIOwe.className = 'debt-dir-btn active py-2.5 px-3 rounded-xl border-2 border-rose-500 bg-rose-950/50 text-xs font-extrabold text-rose-300 flex items-center justify-center gap-1.5 transition-all shadow-sm';
    if (btnOwed) btnOwed.className = 'debt-dir-btn py-2.5 px-3 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-300 flex items-center justify-center gap-1.5 transition-all';
    if (label) label.textContent = 'Кому вы должны?';
  }
}

async function handleCreateDebtSubmit(e) {
  e.preventDefault();
  if (state.isCreatingDebt) return;
  const amtInput = document.getElementById('debtAmountInput');
  const descInput = document.getElementById('debtDescriptionInput');
  const memberSelect = document.getElementById('debtMemberSelect');
  const dueDateInput = document.getElementById('debtDueDateInput');
  const freqSelect = document.getElementById('debtFrequencySelect');
  const customMinsInput = document.getElementById('debtCustomMinutesInput');

  const amount = parseFloat(amtInput?.value || 0);
  const description = (descInput?.value || '').trim();
  const memberId = memberSelect?.value;
  const dueDate = dueDateInput?.value || null;
  const freq = freqSelect?.value || 'daily';
  const customMins = parseInt(customMinsInput?.value || 0) || null;
  const submitButton = document.getElementById('btnSubmitCreateDebt');

  if (!amount || amount <= 0) {
    showToast('Введите корректную сумму', 'error');
    return;
  }
  if (!description) {
    showToast('Введите описание долга', 'error');
    return;
  }
  if (!memberId) {
    showToast('Выберите участника комнаты', 'error');
    return;
  }

  const requestId = state.debtCreateRequestId || (window.crypto?.randomUUID?.() || `debt-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  state.debtCreateRequestId = requestId;
  const payload = {
    amount,
    description,
    direction: state.createDebtDirection,
    is_external: false,
    external_name: null,
    member_user_id: parseInt(memberId),
    due_date: dueDate,
    notification_frequency: freq,
    custom_reminder_interval_minutes: customMins,
    client_request_id: requestId
  };

  state.isCreatingDebt = true;
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.classList.add('opacity-70', 'cursor-wait');
    submitButton.textContent = 'Фиксируем долг…';
  }
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

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Ошибка сервера (${res.status})`);
    showToast(data.message || 'Долг успешно зафиксирован!', 'success');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to create debt:', err);
    showToast(err.message || 'Ошибка при создании долга', 'error');
  } finally {
    state.isCreatingDebt = false;
    state.debtCreateRequestId = null;
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.classList.remove('opacity-70', 'cursor-wait');
      submitButton.innerHTML = '<i data-lucide="check" class="w-4 h-4"></i> Зафиксировать долг';
      refreshIcons();
    }
  }
}

async function openDebtDetailSheet(debtId) {
  let url = `/api/group/${state.groupId}/debts/${debtId}`;
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

    const reminderLabels = { none: 'Выключены', '10_min': 'Каждые 10 минут', '30_min': 'Каждые 30 минут', '3_times_a_day': '3 раза в день', daily: 'Ежедневно', every_3_days: 'Раз в 3 дня', weekly: 'Еженедельно' };
    const freqEl = document.getElementById('debtDetailFrequency');
    if (freqEl) freqEl.textContent = reminderLabels[d.notification_frequency] || 'По графику';
    const reminderSettings = document.getElementById('debtReminderSettings');
    const reminderSelect = document.getElementById('debtReminderFrequencySelect');
    if (reminderSettings) reminderSettings.classList.toggle('hidden', !d.can_manage_reminders || !['active', 'partially_paid'].includes(d.status));
    if (reminderSelect) reminderSelect.value = d.notification_frequency || 'none';

    const canPay = Boolean(d.can_pay) && ['active', 'partially_paid'].includes(d.status) && Number(d.remaining_amount) > 0;
    document.getElementById('btnOpenDebtPaymentSheet')?.classList.toggle('hidden', !canPay);
    document.getElementById('btnMarkDebtPaid')?.classList.toggle('hidden', !canPay);
    document.getElementById('debtPaymentReadOnlyNote')?.classList.toggle('hidden', canPay);

    const paymentsList = document.getElementById('debtDetailPaymentsList');
    if (paymentsList) {
      const payments = d.payments || data.payments || [];
      if (payments.length === 0) {
        paymentsList.innerHTML = '<div class="py-4 text-center text-xs text-slate-400">Платежей пока не было</div>';
      } else {
        paymentsList.innerHTML = payments.map(p => `
          <div class="flex items-center justify-between py-2 text-xs">
            <div>
              <p class="font-bold text-white">${formatCurrency(p.amount)}</p>
              <p class="text-[10px] text-slate-400">${formatDateTime(p.created_at)}</p>
            </div>
            <span class="text-[10px] text-[#00E599] font-bold bg-[#00D29D]/20 border border-[#00D29D]/30 px-2 py-0.5 rounded-full">Оплачено</span>
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
  if (!state.currentDebtDetail.can_pay) {
    showToast('Оплатить можно только долг, который вы должны', 'error');
    return;
  }
  const remEl = document.getElementById('debtPaymentRemainingAmount');
  if (remEl) remEl.textContent = formatCurrency(state.currentDebtDetail.remaining_amount);
  const amtInp = document.getElementById('debtPaymentAmountInput');
  if (amtInp) amtInp.value = state.currentDebtDetail.remaining_amount;
  openSheet('sheet-debt-payment');
}

async function handleDebtPaymentSubmit(e) {
  e.preventDefault();
  if (!state.currentDebtDetail) return;
  if (!state.currentDebtDetail.can_pay) {
    showToast('Оплатить можно только долг, который вы должны', 'error');
    return;
  }
  if (state.isSubmittingDebtPayment) return;

  const amtInput = document.getElementById('debtPaymentAmountInput');
  const noteInput = document.getElementById('debtPaymentNoteInput');
  const amount = parseFloat(amtInput?.value || 0);
  const note = (noteInput?.value || '').trim();

  if (!amount || amount <= 0) {
    showToast('Введите корректную сумму платежа', 'error');
    return;
  }
  if (amount > Number(state.currentDebtDetail.remaining_amount)) {
    showToast('Сумма не может превышать остаток долга', 'error');
    return;
  }
  const requestId = state.debtPaymentRequestId || (window.crypto?.randomUUID?.() || `debt-payment-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  state.debtPaymentRequestId = requestId;
  state.isSubmittingDebtPayment = true;

  try {
    let url = `/api/group/${state.groupId}/debts/${state.currentDebtDetail.id}/payment`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) {
      url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    }

    const res = await fetch(url, {
      method: 'POST',
      headers: getRequestHeaders(),
      body: JSON.stringify({ amount, note, client_request_id: requestId })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    showToast(data.message || 'Платёж зафиксирован!', 'success');
    closeSheets();
    await fetchAndRenderDebts();
  } catch (err) {
    console.error('Failed to submit debt payment:', err);
    showToast('Ошибка при внесении платежа', 'error');
  } finally {
    state.isSubmittingDebtPayment = false;
    state.debtPaymentRequestId = null;
  }
}

async function handleSaveDebtReminders() {
  const debt = state.currentDebtDetail;
  const select = document.getElementById('debtReminderFrequencySelect');
  const button = document.getElementById('btnSaveDebtReminders');
  if (!debt || !select || !debt.can_manage_reminders) return;
  const originalText = button?.textContent;
  if (button) { button.disabled = true; button.textContent = 'Сохраняем…'; }
  try {
    let url = `/api/group/${state.groupId}/debts/${debt.id}/reminders`;
    if (tg?.initDataUnsafe?.user?.id && !tg?.initData) url += `?tg_user_id=${tg.initDataUnsafe.user.id}`;
    const res = await fetch(url, { method: 'POST', headers: getRequestHeaders(), body: JSON.stringify({ notification_frequency: select.value }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    state.currentDebtDetail = data.debt;
    const labels = { none: 'Выключены', '10_min': 'Каждые 10 минут', '30_min': 'Каждые 30 минут', '3_times_a_day': '3 раза в день', daily: 'Ежедневно', every_3_days: 'Раз в 3 дня', weekly: 'Еженедельно' };
    const freqEl = document.getElementById('debtDetailFrequency');
    if (freqEl) freqEl.textContent = labels[data.debt.notification_frequency] || 'По графику';
    showToast(data.message || 'Настройки напоминаний сохранены', 'success');
  } catch (err) {
    console.error('Failed to save debt reminders:', err);
    showToast(err.message || 'Не удалось сохранить напоминания', 'error');
  } finally {
    if (button) { button.disabled = false; button.textContent = originalText || 'Сохранить'; }
  }
}

async function openDebtPaymentFor(debtId) {
  await openDebtDetailSheet(debtId);
  if (Number(state.currentDebtDetail?.id) === Number(debtId)) openDebtPaymentSheet();
}

async function handleMarkDebtPaid() {
  if (!state.currentDebtDetail) return;
  if (!state.currentDebtDetail.can_pay) {
    showToast('Оплатить можно только долг, который вы должны', 'error');
    return;
  }
  if (!await showAppConfirm('Погасить долг?', 'Долг будет отмечен как полностью погашенный.', 'Погасить')) return;

  try {
    let url = `/api/group/${state.groupId}/debts/${state.currentDebtDetail.id}/pay`;
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
  if (!await showAppConfirm('Отменить долг?', 'Долг будет отменён. Это действие нельзя отменить.', 'Отменить', true)) return;

  try {
    let url = `/api/group/${state.groupId}/debts/${state.currentDebtDetail.id}/cancel`;
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
      // API contract: the server stores this value as `budget_limit`, but
      // receives the public request field as `budget`.
      body: JSON.stringify({ budget: limit })
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
  setupAnalyticsSubtabs();
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
  document.getElementById('btnOverviewAiPrevious')?.addEventListener('click', () => changeOverviewAiRecommendation(-1));
  document.getElementById('btnOverviewAiNext')?.addEventListener('click', () => changeOverviewAiRecommendation(1));

  document.getElementById('btnPlanBudget')?.addEventListener('click', savePlanBudget);
  document.getElementById('btnPlanCategoryBudget')?.addEventListener('click', savePlanCategoryBudget);
  document.getElementById('btnPlanRecurring')?.addEventListener('click', addPlanRecurringExpense);

  // Header & Switchers
  const btnGroupSelector = document.getElementById('btnGroupSelector');
  if (btnGroupSelector) btnGroupSelector.addEventListener('click', openGroupSelectorSheet);

  const btnOpenCreateRoom = document.getElementById('btnOpenCreateRoomSheet');
  if (btnOpenCreateRoom) btnOpenCreateRoom.addEventListener('click', openCreateRoomSheet);

  const btnOpenSettings = document.getElementById('btnOpenSettings');
  if (btnOpenSettings) btnOpenSettings.addEventListener('click', () => {
    state.settingsReturnTab = state.activeSheet === 'sheet-add-picker' ? 'add-expense' : state.currentTab;
    switchTab('settings');
  });

  const btnBell = document.getElementById('btnBell');
  if (btnBell) btnBell.addEventListener('click', toggleNotifications);

  // Add-expense header reuses the same room actions as the overview header.
  const btnAddExpenseBell = document.getElementById('btnAddExpenseBell');
  if (btnAddExpenseBell) btnAddExpenseBell.addEventListener('click', toggleNotifications);
  const btnAddExpenseSettings = document.getElementById('btnAddExpenseSettings');
  if (btnAddExpenseSettings) btnAddExpenseSettings.addEventListener('click', () => {
    state.settingsReturnTab = 'add-expense';
    switchTab('settings');
  });

  const btnBackFromSettings = document.getElementById('btnBackFromSettings');
  if (btnBackFromSettings) btnBackFromSettings.addEventListener('click', () => {
    const returnTab = state.settingsReturnTab || 'overview';
    state.settingsReturnTab = 'overview';
    if (returnTab === 'add-expense') { switchTab('overview'); openSheet('sheet-add-picker'); }
    else switchTab(returnTab);
  });

  // Analytics Period Selector
  const btnOpenAnalyticsPeriod = document.getElementById('btnOpenAnalyticsPeriod');
  if (btnOpenAnalyticsPeriod) {
    btnOpenAnalyticsPeriod.addEventListener('click', () => {
      openSheet('sheet-analytics-period');
      updatePeriodModalCheckmarks();
    });
  }

  document.querySelectorAll('.analytics-period-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      const pType = btn.getAttribute('data-period-type');
      if (pType === 'custom') {
        const customBlock = document.getElementById('customDateRangeInputs');
        if (customBlock) customBlock.classList.toggle('hidden');
        return;
      }

      state.analyticsPeriod.type = pType;
      state.analyticsPeriod.from = null;
      state.analyticsPeriod.to = null;
      updatePeriodModalCheckmarks();
      closeSheets();
      fetchAnalytics();
    });
  });

  const btnApplyCustomDateRange = document.getElementById('btnApplyCustomDateRange');
  if (btnApplyCustomDateRange) {
    btnApplyCustomDateRange.addEventListener('click', () => {
      const fromVal = document.getElementById('analyticsCustomDateFrom')?.value;
      const toVal = document.getElementById('analyticsCustomDateTo')?.value;
      if (!fromVal || !toVal) {
        showToast('Пожалуйста, укажите обе даты', 'error');
        return;
      }
      state.analyticsPeriod.type = 'custom';
      state.analyticsPeriod.from = fromVal;
      state.analyticsPeriod.to = toVal;
      updatePeriodModalCheckmarks();
      closeSheets();
      fetchAnalytics();
    });
  }

  // Room Settlement open
  const btnGoToRoomSettlement = document.getElementById('btnGoToRoomSettlement');
  if (btnGoToRoomSettlement) btnGoToRoomSettlement.addEventListener('click', openRoomSettlementSheet);

  const btnSendSettlement = document.getElementById('btnSendSettlementToTelegram');
  if (btnSendSettlement) btnSendSettlement.addEventListener('click', handleSendSettlementTelegram);

  const btnArchiveRoom = document.getElementById('btnArchiveRoomSettings');
  if (btnArchiveRoom) btnArchiveRoom.addEventListener('click', handleArchiveRoom);
  document.getElementById('btnOpenDeleteRoom')?.addEventListener('click', openDeleteRoomConfirmation);
  document.getElementById('btnConfirmDeleteRoom')?.addEventListener('click', handleDeleteRoom);

  // Elevated + Button & Quick Add Banner
  const btnElevatedBot = document.getElementById('btnElevatedBot');
  if (btnElevatedBot) btnElevatedBot.addEventListener('click', () => openSheet('sheet-add-picker'));

  const bannerBotAction = document.getElementById('bannerBotAction');
  if (bannerBotAction) bannerBotAction.addEventListener('click', () => openSheet('sheet-add-picker'));

  // Add Expense Picker options (now opens full screen input modes)
  document.querySelectorAll('.picker-opt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode') || btn.getAttribute('data-target');
      if (mode) {
        const cleanMode = mode.replace(/^sheet-/, '').replace(/-input$/, '');
        openInputMode(cleanMode);
      }
    });
  });

  // Back buttons on all full-screen input modes
  document.querySelectorAll('.btn-back-input').forEach(btn => {
    btn.addEventListener('click', navigateBackFromInputMode);
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
      typeBtnLongTerm.className = 'room-type-btn active py-3 px-3 rounded-xl border-2 border-[#00D29D] bg-[#00D29D]/15 text-xs font-extrabold text-[#00E599] text-center transition-all';
      typeBtnOneTime.className = 'room-type-btn py-3 px-3 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-300 text-center transition-all';
    });
    typeBtnOneTime.addEventListener('click', () => {
      state.createRoomType = 'one_time';
      typeBtnOneTime.className = 'room-type-btn active py-3 px-3 rounded-xl border-2 border-[#00D29D] bg-[#00D29D]/15 text-xs font-extrabold text-[#00E599] text-center transition-all';
      typeBtnLongTerm.className = 'room-type-btn py-3 px-3 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-300 text-center transition-all';
    });
  }

  document.querySelectorAll('.room-cur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.room-cur-btn').forEach(b => {
        b.className = 'room-cur-btn py-2.5 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-300 text-center transition-all';
      });
      btn.className = 'room-cur-btn active py-2.5 rounded-xl border-2 border-[#00D29D] bg-[#00D29D]/15 text-xs font-black text-[#00E599] text-center transition-all';
      state.createRoomCurrency = btn.getAttribute('data-currency') || 'RUB';
    });
  });

  // Sheet close buttons & overlay
  document.querySelectorAll('.close-sheet:not(#sheet-notifications .close-sheet)').forEach(btn => btn.addEventListener('click', closeSheets));
  const btnCloseNotifications = document.querySelector('#sheet-notifications .close-sheet');
  if (btnCloseNotifications) btnCloseNotifications.addEventListener('click', closeNotifications);
  const overlay = document.getElementById('sheetOverlay');
  if (overlay) {
    overlay.addEventListener('mousedown', (e) => {
      if (e.target !== e.currentTarget) return;
      if (state.notificationsOpen) closeNotifications();
      else closeSheets();
    });
  }

  // Quick Add tabs
  const tabBtnQuickAdd = document.getElementById('tabBtnQuickAdd');
  const tabBtnBotTips = document.getElementById('tabBtnBotTips');
  const viewQuickAdd = document.getElementById('viewQuickAdd');
  const viewBotTips = document.getElementById('viewBotTips');

  if (tabBtnQuickAdd && tabBtnBotTips && viewQuickAdd && viewBotTips) {
    tabBtnQuickAdd.addEventListener('click', () => {
      tabBtnQuickAdd.className = 'flex-1 rounded-lg py-2 bg-[#00D29D] text-[#06281E] font-extrabold shadow-sm transition-all';
      tabBtnBotTips.className = 'flex-1 rounded-lg py-2 text-slate-400 font-semibold hover:text-white transition-all';
      viewQuickAdd.classList.remove('hidden');
      viewBotTips.classList.add('hidden');
      refreshIcons();
    });

    tabBtnBotTips.addEventListener('click', () => {
      tabBtnBotTips.className = 'flex-1 rounded-lg py-2 bg-[#00D29D] text-[#06281E] font-extrabold shadow-sm transition-all';
      tabBtnQuickAdd.className = 'flex-1 rounded-lg py-2 text-slate-400 font-semibold hover:text-white transition-all';
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
        p.className = 'cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card';
      });
      pill.className = 'cat-pill active whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-extrabold bg-[#00D29D] text-[#06281E] shadow-card';
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

  const historyDateInput = document.getElementById('historyDateInput');
  const btnHistoryDate = document.getElementById('btnHistoryDate');
  if (btnHistoryDate && historyDateInput) {
    btnHistoryDate.addEventListener('click', () => {
      try {
        if (typeof historyDateInput.showPicker === 'function') historyDateInput.showPicker();
        else historyDateInput.click();
      } catch (err) {
        historyDateInput.focus();
        historyDateInput.click();
      }
    });
    historyDateInput.addEventListener('change', (e) => {
      state.historyDate = e.target.value || '';
      renderHistory();
      refreshIcons();
    });
  }

  // Debts Filter Tabs
  document.querySelectorAll('.debt-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.debt-tab-btn').forEach(b => {
        b.className = 'debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all text-slate-400 hover:text-white text-xs font-semibold';
      });
      btn.className = 'debt-tab-btn active flex-1 py-1.5 rounded-lg text-center transition-all bg-[#00D29D] text-[#06281E] shadow-sm font-extrabold text-xs';
      state.debtFilter = btn.getAttribute('data-debt-filter') || 'all';
      fetchAndRenderDebts();
    });
  });

  const btnOpenCreateDebt = document.getElementById('btnOpenCreateDebt');
  if (btnOpenCreateDebt) btnOpenCreateDebt.addEventListener('click', openCreateDebtSheet);

  const btnInviteRoomMembers = document.getElementById('btnInviteRoomMembers');
  if (btnInviteRoomMembers) btnInviteRoomMembers.addEventListener('click', inviteDebtMember);
  const btnAddFromTelegram = document.getElementById('btnAddFromTelegram');
  if (btnAddFromTelegram) btnAddFromTelegram.addEventListener('click', addFromTelegram);
  const btnMarkNotificationsRead = document.getElementById('btnMarkNotificationsRead');
  if (btnMarkNotificationsRead) btnMarkNotificationsRead.addEventListener('click', markAllNotificationsRead);

  const btnDirOwed = document.getElementById('debtDirOwedToMe');
  if (btnDirOwed) btnDirOwed.addEventListener('click', () => setCreateDebtDirection('owed_to_me'));

  const btnDirIOwe = document.getElementById('debtDirIOwe');
  if (btnDirIOwe) btnDirIOwe.addEventListener('click', () => setCreateDebtDirection('i_owe'));

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
        state.parsedDocumentDraft = null;
        state.documentParticipantIds = [];
        const nameEl = document.getElementById('docFileName');
        const sizeEl = document.getElementById('docFileSize');
        if (nameEl) nameEl.textContent = state.selectedDocFile.name;
        if (sizeEl) sizeEl.textContent = `${Math.round(state.selectedDocFile.size / 1024)} KB · 1 файл`;
        setDocumentImportStatus('Файл выбран', 'loading');
        setDocumentPrimaryAction('Распознаём…', true);
        handleParseDocument();
      }
    });
  }
  if (btnParseDoc) btnParseDoc.addEventListener('click', () => {
    if (!state.selectedDocFile) {
      docInput?.click();
    } else if (!state.parsedDocumentDraft) {
      handleParseDocument();
    } else {
      handleConfirmAttachDoc();
    }
  });

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
          } else {
            return;
          }
        } catch (e) {
          showToast('Не удалось прочитать буфер обмена', 'error');
          return;
        }
      }
      handleParseText();
    });
  }
  const btnParseText = document.getElementById('btnParseTextSubmit');
  if (btnParseText) btnParseText.addEventListener('click', handleSaveTextExpense);
  const rawExpenseTextInput = document.getElementById('rawExpenseTextInput');
  if (rawExpenseTextInput) {
    rawExpenseTextInput.addEventListener('input', () => {
      if (state.lastParsedTextSource !== undefined) resetTextInputPreview();
    });
  }

  // Screen 4: Live Camera Receipt Scanner & OCR
  const btnCapturePhoto = document.getElementById('btnCaptureReceiptPhoto');
  if (btnCapturePhoto) btnCapturePhoto.addEventListener('click', captureReceiptPhoto);

  const btnOpenGallery = document.getElementById('btnReceiptOpenGallery');
  const receiptFileInput = document.getElementById('receiptFileInput');
  if (btnOpenGallery && receiptFileInput) {
    btnOpenGallery.addEventListener('click', () => {
      receiptFileInput.value = '';
      receiptFileInput.click();
    });
  }
  if (receiptFileInput) {
    receiptFileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        handleReceiptGalleryFile(e.target.files[0]);
      }
    });
  }

  const btnRetake = document.getElementById('btnRetakePhoto');
  if (btnRetake) btnRetake.addEventListener('click', startReceiptCamera);

  const btnProcess = document.getElementById('btnProcessPhoto');
  if (btnProcess) btnProcess.addEventListener('click', uploadAndProcessReceipt);

  const btnSwitchCam = document.getElementById('btnReceiptSwitchCamera');
  if (btnSwitchCam) btnSwitchCam.addEventListener('click', switchReceiptCamera);

  const btnTorch = document.getElementById('btnReceiptTorchToggle');
  if (btnTorch) btnTorch.addEventListener('click', toggleReceiptTorch);

  const btnErrRetry = document.getElementById('btnScanErrorRetry');
  if (btnErrRetry) btnErrRetry.addEventListener('click', startReceiptCamera);

  const btnErrGallery = document.getElementById('btnScanErrorGallery');
  if (btnErrGallery && receiptFileInput) {
    btnErrGallery.addEventListener('click', () => {
      receiptFileInput.value = '';
      receiptFileInput.click();
    });
  }

  const btnErrManual = document.getElementById('btnScanErrorManual');
  if (btnErrManual) btnErrManual.addEventListener('click', () => openInputMode('manual'));

  const btnAddRow = document.getElementById('btnAddManualItemRow');
  if (btnAddRow) {
    btnAddRow.addEventListener('click', () => {
      if (!state.parsedReceiptDraft) {
        state.parsedReceiptDraft = {
          merchant: 'Чек покупки',
          total_amount: 0,
          items: []
        };
      }
      const members = state.summary?.members || [{ id: 1 }, { id: 2 }];
      state.parsedReceiptDraft.items.push({
        name: 'Новая позиция',
        quantity: 1,
        unit_price: 100,
        total_amount: 100,
        category: '🍞 Продукты',
        participants: members.map(m => m.id)
      });
      renderParsedItemsList();
      updateReceiptTotals();
    });
  }

  const resMerchantInput = document.getElementById('scanResultMerchant');
  if (resMerchantInput) {
    resMerchantInput.addEventListener('input', (e) => {
      if (state.parsedReceiptDraft) {
        state.parsedReceiptDraft.merchant = e.target.value;
      }
    });
  }

  const resTotalInput = document.getElementById('scanResultTotal');
  if (resTotalInput) {
    resTotalInput.addEventListener('input', updateReceiptTotals);
  }

  const btnSaveReceipt = document.getElementById('btnSaveParsedReceipt');
  if (btnSaveReceipt) btnSaveReceipt.addEventListener('click', handleSaveParsedReceipt);

  window.addEventListener('beforeunload', () => {
    stopReceiptCamera();
    stopVoiceMicrophone();
  });

  // Screen 5: Real Voice Recording & Whisper AI
  const btnVoiceStart = document.getElementById('btnVoiceStartRecord');
  if (btnVoiceStart) btnVoiceStart.addEventListener('click', startVoiceRecording);

  const btnVoiceStop = document.getElementById('btnVoiceStopRecord');
  if (btnVoiceStop) btnVoiceStop.addEventListener('click', stopVoiceRecording);

  const btnVoiceRetake = document.getElementById('btnVoiceRetake');
  if (btnVoiceRetake) btnVoiceRetake.addEventListener('click', resetVoiceRecording);

  const btnVoiceProcess = document.getElementById('btnVoiceProcess');
  if (btnVoiceProcess) btnVoiceProcess.addEventListener('click', uploadAndProcessVoice);

  const btnVoiceRetryErr = document.getElementById('btnVoiceRetryError');
  if (btnVoiceRetryErr) btnVoiceRetryErr.addEventListener('click', resetVoiceRecording);

  const btnVoiceManualFall = document.getElementById('btnVoiceManualFallback');
  if (btnVoiceManualFall) btnVoiceManualFall.addEventListener('click', () => openInputMode('manual'));

  const btnVoiceStartOver = document.getElementById('btnVoiceStartOver');
  if (btnVoiceStartOver) btnVoiceStartOver.addEventListener('click', resetVoiceRecording);

  const btnVoiceAdd = document.getElementById('btnVoiceAddItem');
  if (btnVoiceAdd) {
    btnVoiceAdd.addEventListener('click', () => {
      if (!state.parsedVoiceDraft) {
        state.parsedVoiceDraft = {
          title: 'Голосовой расход',
          total_amount: 0,
          items: []
        };
      }
      const members = state.summary?.members || [{ id: 1 }, { id: 2 }];
      state.parsedVoiceDraft.items.push({
        name: 'Новая позиция',
        quantity: 1,
        unit_price: 100,
        total_amount: 100,
        category: '🍞 Продукты',
        participants: members.map(m => m.id)
      });
      renderVoiceItemsList();
      updateVoiceTotals();
    });
  }

  const voiceTitleInp = document.getElementById('voiceResultTitle');
  if (voiceTitleInp) {
    voiceTitleInp.addEventListener('input', (e) => {
      if (state.parsedVoiceDraft) {
        state.parsedVoiceDraft.title = e.target.value;
      }
    });
  }

  const voiceTotalInp = document.getElementById('voiceResultTotal');
  if (voiceTotalInp) {
    voiceTotalInp.addEventListener('input', updateVoiceTotals);
  }

  const btnSubmitVoice = document.getElementById('btnSubmitVoiceExpense');
  if (btnSubmitVoice) btnSubmitVoice.addEventListener('click', handleSaveVoiceExpense);

  const formDebtPayment = document.getElementById('formDebtPayment');
  if (formDebtPayment) formDebtPayment.addEventListener('submit', handleDebtPaymentSubmit);
  document.getElementById('btnSaveDebtReminders')?.addEventListener('click', handleSaveDebtReminders);

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

  // Network Recovery Retry Button (Sections 24, 47)
  const btnRetry = document.getElementById('btnRetryNetwork');
  if (btnRetry) {
    btnRetry.addEventListener('click', async () => {
      btnRetry.disabled = true;
      btnRetry.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Подключение...';
      refreshIcons();
      try {
        // A retry must run the complete boot sequence. A health-only resume can
        // succeed while the previous room/session request remains broken.
        lifecycle.suspended = false;
        lifecycle.phase = 'BOOTING';
        const recovered = await initApp();
        if (!recovered) {
          showNetworkRecovery(
            'Сервер недоступен по этому адресу',
            'Проверьте интернет. Если он работает, закройте Mini App и откройте её заново из кнопки «Дашборд» в боте — временный адрес мог обновиться.'
          );
          showToast('Не удалось восстановить соединение в этой сессии', 'error');
        }
      } catch (err) {
        showNetworkRecovery(
          'Сервер недоступен по этому адресу',
          'Проверьте интернет. Если он работает, закройте Mini App и откройте её заново из кнопки «Дашборд» в боте.'
        );
        showToast('Сервер пока недоступен. Откройте Mini App заново.', 'error');
      } finally {
        btnRetry.disabled = false;
        btnRetry.innerHTML = '<i data-lucide="rotate-ccw" class="w-4 h-4"></i> Повторить попытку';
        refreshIcons();
      }
    });
  }
  const splashRetry = document.getElementById('splashRetry');
  if (splashRetry) splashRetry.addEventListener('click', async () => {
    splashRetry.classList.add('hidden');
    await initApp();
  });
}

// ── Splash / App Init Sequence ──────────────────────────────
function updateSplash(progress, message) {
  const splash = document.getElementById('splashScreen');
  const bar = document.getElementById('splashProgressBar');
  const status = document.getElementById('splashStatus');
  const track = bar?.parentElement;
  const value = Math.max(0, Math.min(100, Number(progress) || 0));
  if (bar) bar.style.width = `${value}%`;
  if (track) track.setAttribute('aria-valuenow', String(Math.round(value)));
  if (status && message) status.textContent = message;
  return splash;
}

function finishSplash() {
  const splash = document.getElementById('splashScreen');
  document.getElementById('splashRetry')?.classList.add('hidden');
  if (!splash) return;
  updateSplash(100, 'Почти готово…');
  // Hide splash before releasing the startup gate to prevent a raw dual-render frame.
  splash.classList.add('is-hidden');
  document.body.classList.remove('startup-pending');
  lifecycle.phase = 'READY';
}

async function initApp() {
  console.log('[APP_INIT] Starting initialization...');
  updateSplash(4, 'Запускаем SberWise…');
  updateBootDebug({ appMount: 'OK', loaderReason: 'telegram_init' });
  try {
    if (window.Telegram?.WebApp) {
      try {
        initializeTelegramWebApp();
        updateSplash(16, 'Подключаем Telegram…');
        console.log('[TELEGRAM_READY] WebApp expanded, ready=true');
        updateBootDebug({ telegram: 'OK', initData: window.Telegram.WebApp.initData ? 'YES' : 'NO', loaderReason: 'auth' });
        if (window.Telegram.WebApp.BackButton && !telegramBackButtonBound) {
          telegramBackButtonBound = true;
          window.Telegram.WebApp.BackButton.onClick(() => {
            if (state.activeInputMode) {
              navigateBackFromInputMode();
            } else if (state.activeSheet) {
              closeSheets();
            } else if (state.inviteScreenOpen) {
              document.getElementById('inviteAcceptanceScreen')?.remove();
              state.inviteScreenOpen = false;
              ensureWelcomeScreen();
            }
          });
        }
      } catch (e) {
        console.warn('[TELEGRAM_READY_WARN]', e);
      }
    } else {
      updateBootDebug({ telegram: 'FAIL', loaderReason: 'telegram_init' });
    }

    if (!appListenersReady) {
      setupEventListeners();
      appListenersReady = true;
    }
    setupLifecycleController();

    console.log('[AUTH_START] Fetching user and rooms...');
    updateSplash(28, 'Подключаемся к серверу…');
    updateBootDebug({ auth: 'WAIT' });
    const groupsRes = await fetchUserGroupsList();
    updateSplash(58, 'Загружаем ваши комнаты…');
    state.availableGroups = groupsRes.groups || [];
    updateBootDebug({ auth: groupsRes.user ? 'OK' : 'ERROR', rooms: 'OK' });
    if (groupsRes.user) {
      state.currentUser = groupsRes.user;
      console.log('[AUTH_SUCCESS]', { userId: groupsRes.user.id, userName: groupsRes.user.name });
    } else {
      console.log('[AUTH_FALLBACK] Using demo or anonymous session');
    }

    console.log('[ROOMS_LOADED]', { count: state.availableGroups.length });

    const inviteToken = detectInviteToken();
    if (inviteToken) {
      updateSplash(88, 'Проверяем приглашение…');
      await showInviteAcceptanceScreen(inviteToken);
      finishSplash();
      updateBootDebug({ loaderReason: 'none', route: '/invite' });
      return true;
    }

    const detectedId = Number(detectGroupId()) || 0;
    console.info('[LAUNCH_CONTEXT]', { appVersion: APP_VERSION, pathname: location.pathname, search: location.search, hash: location.hash, startParam: tg?.initDataUnsafe?.start_param || null, detectedRoomId: detectedId, launchMode: detectedId ? 'room' : 'generic' });
    updateBootDebug({ launchMode: detectedId ? 'room' : 'generic', route: detectedId ? `/room/${detectedId}` : '/welcome', loaderReason: 'routing' });
    let targetGroupId = null;

    // A normal private/menu launch starts at Welcome. A room deep link keeps the direct dashboard flow.
    if (detectedId === 0) {
      if (groupsRes.requestFailed) {
        updateSplash(42, 'Подключаемся к серверу…');
        document.getElementById('splashRetry')?.classList.remove('hidden');
        showNetworkRecovery();
        return false;
      }
      const mainContent = document.getElementById('mainContent');
      const bottomNav = document.getElementById('bottomNav');
      mainContent?.classList.add('hidden');
      bottomNav?.classList.add('hidden');
      if (mainContent) mainContent.style.display = 'none';
      if (bottomNav) bottomNav.style.display = 'none';
      mainContent?.setAttribute('hidden', '');
      bottomNav?.setAttribute('hidden', '');
      ensureWelcomeScreen();
      updateSplash(88, 'Подготавливаем интерфейс…');
      finishSplash();
      updateBootDebug({ loaderReason: 'none', route: '/welcome' });
      return true;
    }

    if (detectedId !== 0) {
      const found = state.availableGroups.find(g => Number(g.id) === Number(detectedId));
      if (found) {
        targetGroupId = found.id;
      } else if (state.availableGroups.length > 0) {
        targetGroupId = state.availableGroups[0].id;
      } else {
        targetGroupId = detectedId;
      }
    } else if (state.availableGroups.length > 0) {
      targetGroupId = state.availableGroups[0].id;
    } else {
      targetGroupId = 0;
    }

    const currentRoomObj = state.availableGroups.find(g => Number(g.id) === Number(targetGroupId));
    console.log('[CURRENT_ROOM_RESOLVED]', {
      roomsCount: state.availableGroups.length,
      currentRoomId: targetGroupId,
      currentRoomName: currentRoomObj?.name || 'Auto-resolved'
    });

    state.groupId = targetGroupId;
    console.log('[DASHBOARD_LOADING] Requesting summary for group', targetGroupId);
    updateSplash(78, 'Загружаем данные комнаты…');
    await fetchSummary();
    if (state.summary) {
      const mainContent = document.getElementById('mainContent');
      const bottomNav = document.getElementById('bottomNav');
      if (mainContent) mainContent.style.display = '';
      if (bottomNav) bottomNav.style.display = '';
      mainContent?.removeAttribute('hidden');
      bottomNav?.removeAttribute('hidden');
      finishSplash();
      return true;
    }
    return false;

  } catch (err) {
    console.error('[APP_INIT_ERROR]', err);
    updateBootDebug({ loaderReason: 'startup_error', lastError: err.message || String(err) });
    showToast('Не удалось загрузить данные', 'error');
    updateSplash(42, 'Не удалось подключиться к серверу');
    document.getElementById('splashRetry')?.classList.remove('hidden');
    return false;
  } finally {
    refreshIcons();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupLifecycleController();
  initApp();
});
