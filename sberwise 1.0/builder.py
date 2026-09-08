# builder.py - builds index.html matching Figma designs
import os

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")
os.makedirs(WEBAPP_DIR, exist_ok=True)

index_html = """<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>СберСплит — Комнаты и Домашний Бюджет</title>
  
  <!-- Telegram WebApp SDK -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  
  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  
  <!-- Tailwind CSS CDN with Custom Theme -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
          },
          colors: {
            dark: {
              bg: '#0B0F19',
              shell: '#0E1422',
              card: '#151D2E',
              cardHover: '#1B263C',
              border: '#222E46',
              input: '#121A2A',
            },
            mint: {
              300: '#5EEAD4',
              400: '#2DD4BF',
              500: '#00E599',
              600: '#00D29D',
              900: '#06281E',
            },
            cyan: {
              400: '#38BDF8',
              500: '#0EA5E9',
              600: '#00A3FF',
            },
            amber: {
              400: '#FBBF24',
              500: '#F59E0B',
              900: '#1E1B0E',
            },
            indigo: {
              400: '#818CF8',
              500: '#6366F1',
              600: '#5B50E6',
            },
            coral: {
              400: '#F87171',
              500: '#EF4444',
            }
          },
          boxShadow: {
            card: '0 4px 16px rgba(0, 0, 0, 0.25)',
            glowMint: '0 0 24px rgba(0, 229, 153, 0.25)',
            glowAmber: '0 0 24px rgba(245, 158, 11, 0.25)',
            sheet: '0 -10px 30px rgba(0, 0, 0, 0.5)'
          }
        }
      }
    }
  </script>

  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>
  
  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  <link rel="stylesheet" href="style.css">
</head>
<body class="bg-[#0B0F19] font-sans antialiased text-slate-100 select-none">
  <!-- App Shell Container -->
  <div class="flex h-full min-h-screen w-full items-center justify-center sm:p-5">
    <div id="appShell" class="relative h-screen sm:h-[min(900px,calc(100vh-40px))] w-full sm:max-w-[450px] overflow-hidden bg-[#0E1422] sm:rounded-[36px] sm:border sm:border-[#222E46] sm:shadow-2xl flex flex-col">
      
      <!-- Main Scrollable Area -->
      <main id="mainContent" class="no-scrollbar flex-1 overflow-y-auto pb-28">
        
        <!-- SCREEN 1: ОБЗОР КОМНАТЫ -->
        <section id="screen-overview" class="screen-pane">
          <!-- Header -->
          <header class="flex items-center justify-between px-5 pb-4 pt-[max(18px,env(safe-area-inset-top))]">
            <div class="flex items-center gap-3">
              <div class="h-11 w-11 rounded-[16px] border border-[#222E46] bg-[#151D2E] flex items-center justify-center shadow-card text-mint-500">
                <i data-lucide="sparkles" class="w-6 h-6"></i>
              </div>
              <div>
                <p class="text-[11px] font-bold uppercase tracking-wider text-slate-400">СберСплит · Комната</p>
                <button type="button" id="btnGroupSelector" class="inline-flex items-center gap-1.5 hover:opacity-80 active:scale-95 transition-all text-left group">
                  <h1 id="headerTitle" class="text-lg font-extrabold tracking-[-0.03em] text-white truncate max-w-[190px]">Домашний бюджет</h1>
                  <i data-lucide="chevron-down" class="w-4 h-4 text-slate-400 group-hover:text-mint-400 transition-colors shrink-0"></i>
                </button>
              </div>
            </div>
            <div class="flex items-center gap-1.5">
              <button type="button" id="btnBell" class="relative flex h-10 w-10 items-center justify-center rounded-2xl bg-[#151D2E] border border-[#222E46] text-slate-300 hover:text-white transition-colors" aria-label="Уведомления">
                <i data-lucide="bell" class="w-4 h-4"></i>
                <span id="bellDot" class="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-mint-500 shadow-[0_0_8px_#00E599]"></span>
              </button>
              <button type="button" id="btnOpenSettings" class="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#151D2E] border border-[#222E46] text-slate-300 hover:text-white transition-colors" aria-label="Настройки">
                <i data-lucide="settings" class="w-4 h-4"></i>
              </button>
            </div>
          </header>

          <!-- Hero Room Monthly Spend Card -->
          <div class="px-4">
            <div class="rounded-[26px] bg-gradient-to-br from-[#182338] to-[#121A2A] p-5 text-white shadow-card border border-[#2A3956] relative overflow-hidden">
              <div class="absolute -right-8 -bottom-8 w-32 h-32 bg-mint-500/10 rounded-full blur-2xl pointer-events-none"></div>
              <div class="flex items-start justify-between gap-4 relative z-10">
                <div>
                  <div class="flex items-center gap-2">
                    <p class="text-xs font-semibold text-slate-300">Расходы в комнате</p>
                    <span id="overviewRoomTypeBadge" class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#24334D] text-slate-200">Длительная</span>
                  </div>
                  <p id="overviewTotalSpent" class="mt-1 text-[32px] font-black tracking-[-0.04em] text-white">0 ₽</p>
                </div>
                <div class="h-11 w-11 rounded-2xl bg-[#223048] flex items-center justify-center text-mint-400 border border-[#2E4162]">
                  <i data-lucide="wallet-cards" class="w-6 h-6"></i>
                </div>
              </div>
              
              <!-- Progress Bar -->
              <div class="mt-5 h-2 w-full overflow-hidden rounded-full bg-[#202C42]">
                <div id="overviewBudgetBar" class="h-full rounded-full bg-mint-500 transition-all duration-500" style="width: 0%"></div>
              </div>
              
              <div class="mt-2.5 flex justify-between text-xs text-slate-300 font-medium">
                <span id="overviewRemaining">Осталось 0 ₽</span>
                <span id="overviewBudgetRatio">0% из 100 000 ₽</span>
              </div>

              <!-- Sber Alternative Scoring Badge inside Hero -->
              <div id="sberScoringHeroBadge" class="mt-4 pt-3 border-t border-[#25354F] flex items-center justify-between text-xs">
                <div class="flex items-center gap-1.5">
                  <span class="text-mint-400 font-bold flex items-center gap-1">
                    <i data-lucide="shield-check" class="w-4 h-4 text-mint-400"></i>
                    СберСкоринг:
                  </span>
                  <span id="heroScoringGrade" class="px-2 py-0.5 rounded-full bg-mint-500/20 text-mint-300 font-black text-[11px] border border-mint-500/30">820 (AAA)</span>
                </div>
                <span class="text-[11px] text-slate-400 font-medium">Высокая надёжность</span>
              </div>
            </div>
          </div>

          <!-- Room Settlement Card («Итоги комнаты») -->
          <div class="mt-4 px-4">
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46] flex items-center justify-between hover:border-mint-500/40 transition-all cursor-pointer" onclick="openRoomSettlementSheet()">
              <div class="flex items-center gap-3.5">
                <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#10242B] text-mint-400 border border-[#164E43]">
                  <i data-lucide="scale" class="w-5 h-5"></i>
                </span>
                <div>
                  <div class="flex items-center gap-1.5">
                    <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Итоги комнаты</span>
                    <span id="roomStatusBadge" class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-[#1E293B] text-mint-400 border border-[#334155]">Активна</span>
                  </div>
                  <p id="overviewRoomSettlementText" class="text-xs font-black text-white mt-0.5">Все рассчитались · 0 ₽</p>
                </div>
              </div>
              <button type="button" id="btnOpenRoomSettlement" class="rounded-xl bg-[#00D29D] px-3.5 py-2 text-xs font-black text-[#06281E] shadow-sm hover:bg-mint-500 active:scale-95 transition-all flex items-center gap-1">
                Итоги <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
              </button>
            </div>
          </div>

          <!-- Quick Add Expense Banner -->
          <div class="mt-3 px-4">
            <button type="button" id="bannerBotAction" class="flex w-full items-center gap-3 rounded-[22px] border border-[#222E46] bg-[#151D2E] px-4 py-3.5 text-left transition-all active:scale-[0.99] hover:bg-[#1A253A] hover:border-cyan-500/40">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-600/20 text-cyan-400 border border-cyan-500/30 shadow-sm">
                <i data-lucide="plus-circle" class="w-5 h-5"></i>
              </span>
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-extrabold text-white">Внести расход в комнату</span>
                <span class="block truncate text-xs text-slate-400">Чек, голос, текст или вручную</span>
              </span>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500 shrink-0"></i>
            </button>
          </div>

          <!-- Spending Donut Card (На что тратим) -->
          <div class="mt-4 px-4">
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <div class="flex items-center justify-between mb-2">
                <h2 class="text-base font-extrabold text-white">На что тратим</h2>
                <button type="button" class="nav-to-analytics flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300">
                  Подробнее <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
                </button>
              </div>
              <div class="grid grid-cols-[140px_1fr] items-center gap-3 py-1">
                <div class="relative flex items-center justify-center h-[140px] w-[140px] mx-auto">
                  <canvas id="overviewDonutChart" width="140" height="140"></canvas>
                  <div class="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span class="text-[10px] font-bold text-slate-400">Всего</span>
                    <span id="donutCenterTotal" class="text-xs font-black tracking-tight text-white">0 ₽</span>
                  </div>
                </div>
                <div id="overviewTopCategories" class="space-y-2.5 min-w-0">
                  <p class="text-xs text-slate-400">Нет расходов в этом месяце</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent Transactions -->
          <div class="mt-4 px-4">
            <div class="mb-2 flex items-center justify-between px-1">
              <h2 class="text-base font-extrabold text-white">Покупки в комнате</h2>
              <button type="button" class="nav-to-history text-xs font-semibold text-cyan-400 hover:text-cyan-300">Все</button>
            </div>
            <div id="overviewRecentList" class="divide-y divide-[#1D273B] rounded-[24px] bg-[#151D2E] p-1 shadow-card border border-[#222E46]">
              <div class="p-4 text-center text-xs text-slate-400">Загрузка расходов...</div>
            </div>
          </div>
        </section>

        <!-- SCREEN 2: ИСТОРИЯ -->
        <section id="screen-history" class="screen-pane hidden">
          <header class="px-5 pb-3 pt-[max(18px,env(safe-area-inset-top))]">
            <h1 class="text-[24px] font-extrabold tracking-[-0.03em] text-white">История</h1>
            <p id="historySubtitle" class="mt-0.5 text-sm text-slate-400">0 покупок · 0 ₽</p>
          </header>

          <div class="px-4">
            <!-- Search Bar -->
            <label class="flex items-center gap-2 rounded-2xl bg-[#151D2E] px-4 py-3 shadow-card border border-[#222E46] focus-within:border-cyan-500/60">
              <i data-lucide="search" class="w-4 h-4 text-slate-400"></i>
              <input id="historySearchInput" type="text" placeholder="Найти покупку или участника" class="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500">
            </label>

            <!-- Category Pills Filter -->
            <div id="historyCategoryPills" class="no-scrollbar mt-3 flex gap-2 overflow-x-auto pb-1">
              <button type="button" data-category="all" class="cat-pill active whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-extrabold bg-[#00D29D] text-[#06281E] shadow-card">Все</button>
              <button type="button" data-category="🍞 Продукты" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">🍞 Продукты</button>
              <button type="button" data-category="🚗 Транспорт" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">🚗 Транспорт</button>
              <button type="button" data-category="🏠 Жильё" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">🏠 Жильё</button>
              <button type="button" data-category="☕ Кафе" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">☕ Кафе</button>
              <button type="button" data-category="🎉 Развлечения" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">🎉 Развлечения</button>
              <button type="button" data-category="💊 Аптека" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">💊 Аптека</button>
              <button type="button" data-category="🔧 Другое" class="cat-pill whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold bg-[#151D2E] text-slate-300 border border-[#222E46] shadow-card">🔧 Другое</button>
            </div>
          </div>

          <!-- Grouped Transactions List -->
          <div id="historyListContainer" class="mt-4 px-4 space-y-4">
            <div class="rounded-[24px] bg-[#151D2E] p-8 text-center shadow-card border border-[#222E46]">
              <p class="text-sm font-bold text-white">Покупок пока нет</p>
              <p class="mt-1 text-xs text-slate-400">Добавьте первую покупку через кнопку «+» внизу</p>
            </div>
          </div>
        </section>

        <!-- SCREEN 3: АНАЛИТИКА -->
        <section id="screen-analytics" class="screen-pane hidden">
          <header class="flex items-center justify-between px-5 pb-3 pt-[max(18px,env(safe-area-inset-top))]">
            <div>
              <h1 class="text-[24px] font-extrabold tracking-[-0.03em] text-white">Аналитика</h1>
              <p id="analyticsSubtitle" class="mt-0.5 text-sm text-slate-400">Сентябрь 2026</p>
            </div>
            <button type="button" id="btnOpenAnalyticsPeriod" class="whitespace-nowrap rounded-xl bg-[#151D2E] px-3 py-1.5 text-xs font-semibold text-slate-300 border border-[#222E46] flex items-center gap-1.5 hover:bg-[#1A253A] active:scale-95 transition-all cursor-pointer">
              <i data-lucide="calendar" class="w-3.5 h-3.5 text-[#00E599]"></i>
              <span id="analyticsPeriodButtonLabel">Сентябрь</span>
              <i data-lucide="chevron-down" class="w-3.5 h-3.5 text-slate-400"></i>
            </button>
          </header>

          <div class="grid grid-cols-2 gap-3 px-4">
            <div class="rounded-2xl bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <p class="text-xs text-slate-400">Средний чек</p>
              <div class="mt-2 flex items-center gap-1 text-white">
                <span id="analyticsAvgCheck" class="text-xl font-extrabold">0 ₽</span>
              </div>
              <p class="mt-1 text-xs text-mint-400 flex items-center gap-0.5">
                <i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i> <span id="analyticsAvgNote">оптимально</span>
              </p>
            </div>
            <div class="rounded-2xl bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <p class="text-xs text-slate-400">Кол-во покупок</p>
              <div class="mt-2 flex items-center gap-1 text-cyan-400">
                <span id="analyticsTxCount" class="text-xl font-extrabold">0</span>
              </div>
              <p id="analyticsTxCountNote" class="mt-1 text-xs text-slate-400">за период</p>
            </div>
          </div>

          <div class="mt-4 px-4">
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <div class="flex items-start justify-between">
                <div>
                  <h2 id="analyticsTimelineTitle" class="text-base font-extrabold text-white">Динамика по неделям</h2>
                  <p id="analyticsTimelineSubtitle" class="mt-0.5 text-xs text-slate-400">Распределение расходов</p>
                </div>
                <strong id="analyticsTotalBadge" class="text-sm text-white font-extrabold">0 ₽</strong>
              </div>
              <div class="mt-4 h-[180px] w-full">
                <canvas id="analyticsWeeklyChart"></canvas>
              </div>
            </div>
          </div>

          <div class="mt-4 px-4">
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <h2 class="text-base font-extrabold text-white mb-3">Категории расходов</h2>
              <div id="analyticsCategoriesList" class="space-y-4">
                <p class="text-xs text-slate-400">За выбранный период расходов нет</p>
              </div>
            </div>
          </div>
        </section>

        <!-- SCREEN 4: БАЛАНС & ДОЛГИ (ИТОГИ) -->
        <section id="screen-family" class="screen-pane hidden">
          <header class="flex items-center justify-between px-5 pb-3 pt-[max(18px,env(safe-area-inset-top))]">
            <div>
              <h1 class="text-[24px] font-extrabold tracking-[-0.03em] text-white">Итоги & Долги</h1>
              <p id="familySubtitle" class="mt-0.5 text-sm text-slate-400">Взаиморасчёты и долговые обязательства</p>
            </div>
            <div class="flex items-center gap-2">
              <button type="button" id="btnOpenCreateDebt" class="flex items-center gap-1.5 rounded-2xl bg-[#00D29D] px-3.5 py-2.5 text-xs font-black text-[#06281E] shadow-card active:scale-95 transition-transform hover:bg-mint-500">
                <i data-lucide="plus-circle" class="w-4 h-4"></i>
                <span>+ Долг</span>
              </button>
            </div>
          </header>

          <!-- Room Settlement Highlights Banner -->
          <div class="px-4">
            <div class="rounded-[24px] bg-[#151D2E] p-5 text-white shadow-card border border-[#222E46] relative overflow-hidden">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs font-semibold text-slate-400">Оптимизация переводов комнаты</p>
                  <h2 id="familyDebtsStatus" class="mt-1 text-xl font-black text-white">Все рассчитались</h2>
                </div>
                <button type="button" id="btnGoToRoomSettlement" class="px-3.5 py-2 rounded-xl bg-[#00D29D] text-[#06281E] font-black text-xs hover:bg-mint-500 transition-all">
                  Итоги комнаты
                </button>
              </div>
              <p class="mt-3 text-xs leading-5 text-slate-300">
                Алгоритм СберСплита минимизирует количество банковских переводов между участниками до кратчайшего пути.
              </p>
            </div>
          </div>

          <!-- Debts Summary Stat Cards -->
          <div class="mt-4 px-4">
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-[22px] bg-[#10242B] border border-[#164E43] p-3.5 shadow-card">
                <div class="flex items-center justify-between">
                  <span class="text-[11px] font-bold text-mint-400 uppercase tracking-wider">Мне должны</span>
                  <div class="h-6 w-6 rounded-full bg-mint-500/20 flex items-center justify-center text-mint-400">
                    <i data-lucide="arrow-down-left" class="w-3.5 h-3.5"></i>
                  </div>
                </div>
                <p id="debtsOwedToMeTotal" class="mt-1 text-[20px] font-black text-[#00E599]">0 ₽</p>
              </div>
              <div class="rounded-[22px] bg-[#2A151D] border border-[#52222E] p-3.5 shadow-card">
                <div class="flex items-center justify-between">
                  <span class="text-[11px] font-bold text-coral-400 uppercase tracking-wider">Я должен</span>
                  <div class="h-6 w-6 rounded-full bg-coral-500/20 flex items-center justify-center text-coral-400">
                    <i data-lucide="arrow-up-right" class="w-3.5 h-3.5"></i>
                  </div>
                </div>
                <p id="debtsIOweTotal" class="mt-1 text-[20px] font-black text-coral-400">0 ₽</p>
              </div>
            </div>
          </div>

          <!-- Debts Management Section -->
          <div class="mt-4 px-4">
            <div class="flex items-center justify-between mb-2.5 px-1">
              <h2 class="text-base font-extrabold text-white">Учёт долгов и напоминаний</h2>
              <span id="debtsCountBadge" class="px-2 py-0.5 rounded-full bg-[#1A2538] text-slate-300 text-[11px] font-bold">0 активных</span>
            </div>

            <!-- Filter Tabs -->
            <div class="flex items-center p-1 bg-[#151D2E] border border-[#222E46] rounded-xl mb-3 text-xs font-semibold">
              <button type="button" class="debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all bg-[#222E46] text-white shadow-sm font-bold" data-debt-filter="all">
                Все
              </button>
              <button type="button" class="debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all text-slate-400 hover:text-white" data-debt-filter="owed_to_me">
                Мне должны
              </button>
              <button type="button" class="debt-tab-btn flex-1 py-1.5 rounded-lg text-center transition-all text-slate-400 hover:text-white" data-debt-filter="i_owe">
                Я должен
              </button>
            </div>

            <div id="debtsListContainer" class="space-y-2.5">
              <div class="py-6 text-center text-xs text-slate-400">
                Загрузка долгов...
              </div>
            </div>
          </div>

          <!-- Members -->
          <div class="mt-5 px-4">
            <div class="mb-2 flex items-center justify-between px-1">
              <h2 class="text-base font-extrabold text-white">Участники комнаты</h2>
              <span class="text-xs text-cyan-400 font-semibold">Сбер FICO Рейтинг</span>
            </div>
            <div id="familyMembersList" class="divide-y divide-[#1D273B] rounded-[24px] bg-[#151D2E] px-4 shadow-card border border-[#222E46]">
              <div class="py-4 text-center text-xs text-slate-400">Загрузка участников...</div>
            </div>
          </div>
        </section>

        <!-- SCREEN 5: НАСТРОЙКИ -->
        <section id="screen-settings" class="screen-pane hidden">
          <header class="flex items-center gap-3 px-4 pb-4 pt-[max(18px,env(safe-area-inset-top))]">
            <button type="button" id="btnBackFromSettings" class="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#151D2E] border border-[#222E46] text-slate-300 hover:text-white transition-transform active:scale-95" aria-label="Назад">
              <i data-lucide="chevron-left" class="w-5 h-5"></i>
            </button>
            <div>
              <h1 class="text-[24px] font-extrabold tracking-[-0.03em] text-white">Настройки</h1>
              <p class="text-sm text-slate-400">Параметры комнаты и профиль</p>
            </div>
          </header>

          <div class="mx-4 rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
            <div class="flex items-center gap-3">
              <div id="settingsUserAvatar" class="h-12 w-12 rounded-2xl bg-cyan-600/20 text-cyan-400 border border-cyan-500/40 flex items-center justify-center font-black text-base shadow-sm">
                Я
              </div>
              <div class="min-w-0 flex-1">
                <p id="settingsUserName" class="font-bold text-white">Пользователь</p>
                <p id="settingsUserRole" class="truncate text-xs text-slate-400">Участник сплит-комнаты</p>
              </div>
              <span class="px-2.5 py-1 rounded-full bg-mint-500/20 text-mint-400 border border-mint-500/30 font-bold text-xs">Активен</span>
            </div>
          </div>

          <div class="mt-5 px-4">
            <h2 class="mb-2 px-1 text-sm font-extrabold text-white">Лимит расходов комнаты</h2>
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46]">
              <label class="text-xs font-semibold text-slate-400" for="inputBudgetLimit">Лимит на период (₽)</label>
              <div class="mt-2 flex gap-2">
                <div class="flex min-w-0 flex-1 items-center rounded-xl border border-[#222E46] bg-[#0E1422] px-3 focus-within:border-cyan-500/60">
                  <input id="inputBudgetLimit" type="number" inputmode="numeric" value="100000" class="min-w-0 flex-1 py-2.5 text-base font-black text-white bg-transparent outline-none">
                  <span class="text-sm text-slate-400 font-bold">₽</span>
                </div>
                <button type="button" id="btnSaveBudgetLimit" class="rounded-xl bg-[#00D29D] px-4 text-sm font-black text-[#06281E] shadow-sm hover:bg-mint-500 transition-transform active:scale-95">
                  Сохранить
                </button>
              </div>
            </div>
          </div>

          <div class="mt-5 px-4">
            <h2 class="mb-2 px-1 text-sm font-extrabold text-white">Управление комнатой</h2>
            <div class="rounded-[24px] bg-[#151D2E] p-4 shadow-card border border-[#222E46] space-y-3">
              <div>
                <h3 class="text-sm font-bold text-white">Завершить и закрыть комнату</h3>
                <p class="text-xs text-slate-400 mt-0.5">
                  Фиксирует финальный расчёт и переводит комнату в архив.
                </p>
                <button type="button" id="btnArchiveRoomSettings" class="mt-2.5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#1E293B] border border-[#334155] px-4 py-2.5 text-xs font-bold text-slate-200 transition-colors hover:bg-[#28354A]">
                  <i data-lucide="archive" class="w-4 h-4"></i> Зафиксировать итоги и архивировать
                </button>
              </div>
            </div>
          </div>
        </section>

      </main>

      <!-- Bottom Navigation Bar -->
      <nav id="bottomNav" class="absolute inset-x-0 bottom-0 z-30 border-t border-[#222E46] bg-[#0E1422]/95 px-2 pb-[max(8px,env(safe-area-inset-bottom))] pt-2 backdrop-blur">
        <div class="grid grid-cols-5 items-end">
          <!-- 1: Overview -->
          <button type="button" data-tab="overview" class="nav-btn active flex min-w-0 flex-col items-center gap-1 px-1 py-1 text-mint-400 transition-colors focus:outline-none">
            <i data-lucide="home" class="w-5 h-5"></i>
            <span class="whitespace-nowrap text-[10px] font-bold">Комната</span>
          </button>
          
          <!-- 2: History -->
          <button type="button" data-tab="history" class="nav-btn flex min-w-0 flex-col items-center gap-1 px-1 py-1 text-slate-400 transition-colors focus:outline-none">
            <i data-lucide="history" class="w-5 h-5"></i>
            <span class="whitespace-nowrap text-[10px] font-semibold">История</span>
          </button>

          <!-- 3: Elevated Center Add Expense Button -->
          <button type="button" id="btnElevatedBot" class="group flex flex-col items-center gap-1 focus:outline-none -mt-6">
            <span class="flex h-14 w-14 items-center justify-center rounded-[22px] border-4 border-[#0E1422] bg-[#00D29D] text-[#06281E] shadow-glowMint transition-transform duration-150 active:scale-95 hover:bg-mint-500">
              <i data-lucide="plus" class="w-7 h-7"></i>
            </span>
            <span class="text-[10px] font-black text-mint-400">+ Расход</span>
          </button>

          <!-- 4: Analytics -->
          <button type="button" data-tab="analytics" class="nav-btn flex min-w-0 flex-col items-center gap-1 px-1 py-1 text-slate-400 transition-colors focus:outline-none">
            <i data-lucide="chart-no-axes-combined" class="w-5 h-5"></i>
            <span class="whitespace-nowrap text-[10px] font-semibold">Аналитика</span>
          </button>

          <!-- 5: Balances & Debts -->
          <button type="button" data-tab="family" class="nav-btn flex min-w-0 flex-col items-center gap-1 px-1 py-1 text-slate-400 transition-colors focus:outline-none">
            <i data-lucide="scale" class="w-5 h-5"></i>
            <span class="whitespace-nowrap text-[10px] font-semibold">Итоги</span>
          </button>
        </div>
      </nav>

      <!-- BOTTOM SHEETS CONTAINER OVERLAY -->
      <div id="sheetOverlay" class="absolute inset-0 z-50 flex items-end bg-black/75 transition-opacity duration-200 hidden opacity-0">
        
        <!-- SHEET 0: ADD EXPENSE PICKER (5 WAYS) -->
        <section id="sheet-add-picker" class="sheet-content no-scrollbar max-h-[88%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <div>
              <h2 class="text-lg font-black tracking-[-0.02em] text-white">Внести расход</h2>
              <p class="text-xs text-slate-400">Выберите удобный способ добавления</p>
            </div>
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 focus:outline-none hover:text-white transition-colors">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>
          
          <div class="px-5 py-4 space-y-2.5">
            <!-- 1: Manual -->
            <button type="button" class="picker-opt-btn flex w-full items-center gap-3.5 p-3.5 rounded-2xl border border-[#222E46] bg-[#151D2E] hover:bg-[#1A253A] active:scale-[0.99] transition-all text-left shadow-sm" data-target="sheet-bot">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-700/40 text-slate-300 border border-slate-600/30">
                <i data-lucide="keyboard" class="w-5 h-5"></i>
              </span>
              <div class="flex-1 min-w-0">
                <h4 class="text-sm font-extrabold text-white">Вручную</h4>
                <p class="text-xs text-slate-400">Сумма, категория, выбор кто платил и на кого делить</p>
              </div>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500"></i>
            </button>

            <!-- 2: Text Parse -->
            <button type="button" class="picker-opt-btn flex w-full items-center gap-3.5 p-3.5 rounded-2xl border border-[#222E46] bg-[#151D2E] hover:bg-[#1A253A] active:scale-[0.99] transition-all text-left shadow-sm" data-target="sheet-text-input">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                <i data-lucide="sparkles" class="w-5 h-5"></i>
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <h4 class="text-sm font-extrabold text-white">Текстовый ввод</h4>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">AI</span>
                </div>
                <p class="text-xs text-slate-400">Вставьте сообщение из мессенджера или список</p>
              </div>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500"></i>
            </button>

            <!-- 3: Voice -->
            <button type="button" class="picker-opt-btn flex w-full items-center gap-3.5 p-3.5 rounded-2xl border border-[#222E46] bg-[#151D2E] hover:bg-[#1A253A] active:scale-[0.99] transition-all text-left shadow-sm" data-target="sheet-voice-input">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30">
                <i data-lucide="mic" class="w-5 h-5"></i>
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <h4 class="text-sm font-extrabold text-white">Голосовой ввод расхода</h4>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/30">Whisper AI</span>
                </div>
                <p class="text-xs text-slate-400">Нейросеть расшифрует и сгруппирует суммы</p>
              </div>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500"></i>
            </button>

            <!-- 4: Photo Receipt -->
            <button type="button" class="picker-opt-btn flex w-full items-center gap-3.5 p-3.5 rounded-2xl border border-[#222E46] bg-[#151D2E] hover:bg-[#1A253A] active:scale-[0.99] transition-all text-left shadow-sm" data-target="sheet-scan-receipt">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-mint-500/20 text-mint-400 border border-mint-500/30">
                <i data-lucide="camera" class="w-5 h-5"></i>
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <h4 class="text-sm font-extrabold text-white">Сканирование чека</h4>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-mint-500/20 text-mint-300 border border-mint-500/30">OCR AI</span>
                </div>
                <p class="text-xs text-slate-400">QR-код ФНС и оптическое распознавание позиций</p>
              </div>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500"></i>
            </button>

            <!-- 5: Document PDF/CSV -->
            <button type="button" class="picker-opt-btn flex w-full items-center gap-3.5 p-3.5 rounded-2xl border border-[#222E46] bg-[#151D2E] hover:bg-[#1A253A] active:scale-[0.99] transition-all text-left shadow-sm" data-target="sheet-upload-doc">
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                <i data-lucide="file-text" class="w-5 h-5"></i>
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5">
                  <h4 class="text-sm font-extrabold text-white">Импорт электронного чека</h4>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">PDF/CSV</span>
                </div>
                <p class="text-xs text-slate-400">Ozon Travel, билеты, бронирования и выписки</p>
              </div>
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-500"></i>
            </button>
          </div>
        </section>

        <!-- FIGMA SCREEN 1: ИТОГИ КОМНАТЫ (Exact match to media_1788523300056.jpg) -->
        <section id="sheet-room-settlement" class="sheet-content no-scrollbar max-h-[92%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-base font-extrabold text-white">Итоги комнаты</h2>
            <button type="button" class="flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors" onclick="handleSendSettlementTelegram()">
              <i data-lucide="share-2" class="w-4 h-4"></i>
            </button>
          </div>

          <div class="px-5 py-4 space-y-4">
            <!-- Hero Card: Ваш личный результат -->
            <div id="settlementPersonalBox" class="rounded-[24px] p-5 text-center shadow-card bg-[#10242B] border border-[#164E43] relative overflow-hidden">
              <p class="text-xs font-bold text-mint-400">Ваш личный результат</p>
              <p id="settlementPersonalAmount" class="mt-1 text-[34px] font-black tracking-tight text-[#00E599]">+6 094 ₽</p>
              <p id="settlementPersonalNote" class="text-xs text-slate-400 mt-1">Вам должны перевести участники</p>
            </div>

            <!-- Transfers Section Header -->
            <div>
              <div class="flex items-center justify-between mb-2.5 px-1">
                <span class="text-xs font-bold text-white">Кому и сколько перевести</span>
                <span id="settlementTransfersCount" class="text-xs text-slate-400">2 перевода</span>
              </div>
              <div id="settlementTransfersList" class="space-y-2.5">
                <!-- Example matching Figma -->
                <div class="flex items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] shadow-sm">
                  <div class="flex items-center gap-3">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-[#222E46] text-slate-200 font-extrabold text-xs">
                      КТ
                    </span>
                    <div>
                      <h4 class="text-sm font-extrabold text-white">Участник комнаты</h4>
                      <p class="text-[11px] text-slate-400">переводит вам</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="px-2 py-0.5 rounded-lg text-xs font-extrabold bg-[#1A2832] text-cyan-400 border border-cyan-500/20">Ждем</span>
                    <span class="text-sm font-black text-[#00E599]">+3 711 ₽</span>
                  </div>
                </div>

                <div class="flex items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] shadow-sm">
                  <div class="flex items-center gap-3">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-700/30 text-cyan-300 font-extrabold text-xs border border-cyan-500/30">
                      МВ
                    </span>
                    <div>
                      <h4 class="text-sm font-extrabold text-white">Другой участник</h4>
                      <p class="text-[11px] text-slate-400">переводит вам</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="px-2 py-0.5 rounded-lg text-xs font-extrabold bg-[#10242B] text-mint-400 border border-mint-500/20">СБП</span>
                    <span class="text-sm font-black text-[#00E599]">+2 383 ₽</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Linked Card info (from Figma) -->
            <div class="rounded-2xl bg-[#151D2E] p-3.5 border border-[#222E46] flex items-center justify-between text-xs">
              <div class="flex items-center gap-2 text-slate-400">
                <i data-lucide="credit-card" class="w-4 h-4 text-slate-400"></i>
                <span>Привязана карта:</span>
              </div>
              <span class="font-bold text-white">****</span>
            </div>

            <!-- Bottom CTA Button (Figma exact) -->
            <div class="pt-2">
              <button type="button" id="btnSendSettlementToTelegram" class="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#00D29D] py-3.5 text-sm font-black text-[#06281E] shadow-glowMint transition-all hover:bg-mint-500 active:scale-95">
                <i data-lucide="share-2" class="w-4 h-4"></i>
                Отправить сводку в чат Telegram
              </button>
            </div>
          </div>
        </section>

        <!-- SHEET: ВЫБОР ПЕРИОДА АНАЛИТИКИ -->
        <section id="sheet-analytics-period" class="sheet-content no-scrollbar max-h-[85%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <div class="flex items-center gap-2">
              <i data-lucide="calendar" class="w-5 h-5 text-[#00E599]"></i>
              <h2 class="text-base font-extrabold text-white">Период аналитики</h2>
            </div>
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>

          <div class="p-5 space-y-2.5">
            <!-- 1. Текущий месяц -->
            <button type="button" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="current_month">
              <div>
                <p class="text-sm font-bold text-white">Текущий месяц</p>
                <p id="periodOptCurrentMonthSub" class="text-xs text-slate-400 mt-0.5">Сентябрь 2026</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4"></i>
              </div>
            </button>

            <!-- 2. Прошлый месяц -->
            <button type="button" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="prev_month">
              <div>
                <p class="text-sm font-bold text-white">Прошлый месяц</p>
                <p id="periodOptPrevMonthSub" class="text-xs text-slate-400 mt-0.5">Август 2026</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4 hidden"></i>
              </div>
            </button>

            <!-- 3. Последние 7 дней -->
            <button type="button" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="7_days">
              <div>
                <p class="text-sm font-bold text-white">Последние 7 дней</p>
                <p class="text-xs text-slate-400 mt-0.5">Посуточная динамика трат</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4 hidden"></i>
              </div>
            </button>

            <!-- 4. Последние 30 дней -->
            <button type="button" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="30_days">
              <div>
                <p class="text-sm font-bold text-white">Последние 30 дней</p>
                <p class="text-xs text-slate-400 mt-0.5">Динамика за 30 дней по неделям</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4 hidden"></i>
              </div>
            </button>

            <!-- 5. Всё время -->
            <button type="button" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="all_time">
              <div>
                <p class="text-sm font-bold text-white">Всё время</p>
                <p class="text-xs text-slate-400 mt-0.5">Вся история текущей комнаты</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4 hidden"></i>
              </div>
            </button>

            <!-- 6. Выбрать даты -->
            <button type="button" id="btnPeriodCustomToggle" class="analytics-period-opt flex w-full items-center justify-between p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] hover:bg-[#1C263B] transition-all text-left" data-period-type="custom">
              <div>
                <p class="text-sm font-bold text-white">Выбрать даты</p>
                <p class="text-xs text-slate-400 mt-0.5">Произвольный диапазон</p>
              </div>
              <div class="period-check-icon w-6 h-6 rounded-full border border-[#222E46] bg-[#101726] flex items-center justify-center text-[#00E599]">
                <i data-lucide="check" class="w-4 h-4 hidden"></i>
              </div>
            </button>

            <!-- Custom date range block -->
            <div id="customDateRangeInputs" class="hidden rounded-2xl bg-[#101726] border border-[#222E46] p-4 space-y-3 mt-1">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="text-[11px] font-bold text-slate-400 block mb-1">Дата начала</label>
                  <input type="date" id="analyticsCustomDateFrom" class="w-full bg-[#151D2E] border border-[#222E46] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#00D29D]">
                </div>
                <div>
                  <label class="text-[11px] font-bold text-slate-400 block mb-1">Дата окончания</label>
                  <input type="date" id="analyticsCustomDateTo" class="w-full bg-[#151D2E] border border-[#222E46] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#00D29D]">
                </div>
              </div>
              <button type="button" id="btnApplyCustomDateRange" class="w-full py-2.5 rounded-xl bg-[#00D29D] text-[#06281E] font-black text-xs hover:bg-mint-500 active:scale-95 transition-all">
                Применить даты
              </button>
            </div>
          </div>
        </section>

        <!-- FIGMA SCREEN 2: ИМПОРТ ЭЛЕКТРОННОГО ЧЕКА PDF/CSV (Exact match to media_1788523300058.jpg) -->
        <section id="sheet-upload-doc" class="sheet-content no-scrollbar max-h-[92%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-base font-extrabold text-white">Импорт электронного чека</h2>
            <span class="text-xs font-extrabold text-[#818CF8]">PDF/CSV</span>
          </div>
          
          <div class="px-5 py-4 space-y-4">
            <input type="file" id="docFileInput" accept=".pdf,.csv,text/csv,application/pdf" class="hidden">

            <!-- File card (Figma exact) -->
            <div id="docFileCardFigma" class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-4 flex items-center justify-between cursor-pointer hover:border-indigo-500/50 transition-all">
              <div class="flex items-center gap-3 min-w-0">
                <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-500/20 text-[#818CF8] border border-indigo-500/30">
                  <i data-lucide="file-text" class="w-6 h-6"></i>
                </div>
                <div class="min-w-0">
                  <h4 id="docFileName" class="text-sm font-extrabold text-white truncate">Ozon_Travel_Booking_883.pdf</h4>
                  <p id="docFileSize" class="text-xs text-slate-400 mt-0.5">340 КБ · Загружен из Telegram</p>
                  <p class="text-xs font-bold text-mint-400 mt-1 flex items-center gap-1">
                    <span class="h-1.5 w-1.5 rounded-full bg-mint-500"></span>
                    Файл проверен и распарсен
                  </p>
                </div>
              </div>
              <button type="button" id="btnDocTriggerSelect" class="text-slate-400 hover:text-white p-2">
                <i data-lucide="upload-cloud" class="w-5 h-5"></i>
              </button>
            </div>

            <!-- Данные из документа -->
            <div>
              <p class="text-xs font-bold text-slate-400 mb-2 px-1">Данные из документа:</p>
              <div class="rounded-2xl bg-[#151D2E] border border-[#222E46] p-4 space-y-3">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-slate-400">Услуга:</span>
                  <span id="docServiceName" class="font-extrabold text-white">Аренда коттеджа (2 ночи)</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                  <span class="text-slate-400">Даты:</span>
                  <span id="docServiceDates" class="font-extrabold text-white">16 авг — 18 авг</span>
                </div>
                <div class="flex items-center justify-between pt-2 border-t border-[#222E46]">
                  <span id="docTotalAmountDisplay" class="text-xl font-black text-white">22 270 ₽</span>
                  <span class="text-xs font-medium text-slate-400">Общий счет:</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                  <span class="text-slate-400">Разделение:</span>
                  <span class="font-extrabold text-mint-400">Поровну на всех (4 чел)</span>
                </div>
              </div>
            </div>

            <!-- Доля на каждого участника (Figma exact highlight card) -->
            <div class="rounded-2xl bg-[#0B2A22] border border-[#134E3F] p-4 flex items-center justify-between">
              <div>
                <p class="text-xs font-extrabold text-mint-400">Доля на каждого участника</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Включая уборку и депозит</p>
              </div>
              <p id="docMyShareDisplay" class="text-lg font-black text-[#00E599]">5 567,50 ₽</p>
            </div>

            <!-- Bottom CTA Button (Figma exact) -->
            <button type="button" id="btnParseDocSubmit" class="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#5B50E6] py-3.5 text-sm font-black text-white shadow-lg transition-all hover:bg-[#6D62F7] active:scale-95">
              Прикрепить PDF к расходам
            </button>
          </div>
        </section>

        <!-- FIGMA SCREEN 3: ТЕКСТОВЫЙ ВВОД (Exact match to media_1788523300061.jpg) -->
        <section id="sheet-text-input" class="sheet-content no-scrollbar max-h-[92%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-base font-extrabold text-white">Текстовый ввод</h2>
            <button type="button" id="btnPasteFromClipboard" class="text-xs font-extrabold text-cyan-400 hover:text-cyan-300 transition-colors">
              Вставить
            </button>
          </div>
          
          <div class="px-5 py-4 space-y-4">
            <p class="text-xs text-slate-400">Вставьте сообщение из мессенджера или список покупок</p>
            
            <!-- Textarea Card (Figma exact) -->
            <div class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-3.5">
              <textarea id="rawExpenseTextInput" rows="5" class="w-full bg-transparent text-xs leading-relaxed text-slate-200 placeholder:text-slate-500 outline-none font-mono resize-none">Пицца пепперони 2 шт — 1600
Сет роллов Филадельфия — 2400 (только Аня и Мария)
Морс и лимонады — 650
Доставка Яндекс Еда — 290</textarea>
            </div>

            <!-- Распознано участников -->
            <div>
              <div class="flex items-center justify-between mb-2 text-xs px-1">
                <span class="font-bold text-slate-400">Распознано участников:</span>
                <span id="textParsedMembersCount" class="font-extrabold text-mint-400">4 персоны</span>
              </div>
              <div id="textParsedPillsContainer" class="flex flex-wrap gap-2">
                <span class="px-3 py-1.5 rounded-xl bg-[#1E293B] border border-[#334155] text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                  <i data-lucide="user" class="w-3.5 h-3.5 text-cyan-400"></i> Участник (2 позиции)
                </span>
                <span class="px-3 py-1.5 rounded-xl bg-[#1E293B] border border-[#334155] text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                  <i data-lucide="user" class="w-3.5 h-3.5 text-cyan-400"></i> Другой участник (2 позиции)
                </span>
                <span class="px-3 py-1.5 rounded-xl bg-[#1E293B] border border-[#334155] text-xs font-semibold text-slate-200">
                  Все остальные (2 позиции)
                </span>
              </div>
            </div>

            <!-- Summary Box (Figma exact) -->
            <div class="rounded-2xl bg-[#151D2E] border border-[#222E46] p-4 space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-slate-400">Итого сумма по чеку:</span>
                <span id="textTotalAmountDisplay" class="font-black text-white text-sm">4 940 ₽</span>
              </div>
              <div class="flex items-center justify-between text-xs pt-1 border-t border-[#222E46]">
                <span class="text-slate-400">Кто оплатил:</span>
                <span id="textPayerDisplay" class="font-extrabold text-mint-400">Вы</span>
              </div>
            </div>

            <!-- Bottom CTA Button (Figma exact) -->
            <button type="button" id="btnParseTextSubmit" class="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#00A3FF] py-3.5 text-sm font-black text-white shadow-lg transition-all hover:bg-[#1DAEFF] active:scale-95">
              <i data-lucide="zap" class="w-4 h-4"></i>
              Рассчитать и сохранить чек
            </button>
          </div>
        </section>

        <!-- FIGMA SCREEN 4: СКАНИРОВАНИЕ ЧЕКА & OCR (Exact match to media_1788523300064.jpg) -->
        <section id="sheet-scan-receipt" class="sheet-content no-scrollbar max-h-[92%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          
          <!-- Top Bar from Figma: 1 607 ₽ Ваша часть к оплате + Кнопка подтвердить -->
          <div class="sticky top-0 z-20 bg-[#0E1422] border-b border-[#222E46] px-5 py-3 flex items-center justify-between">
            <div>
              <p id="scanMyShareDisplay" class="text-xl font-black text-[#00E599]">1 607 ₽</p>
              <p class="text-[11px] text-slate-400">Ваша часть к оплате:</p>
            </div>
            <button type="button" id="btnConfirmScanReceipt" class="flex items-center gap-1.5 rounded-xl bg-[#00D29D] px-3.5 py-2.5 text-xs font-black text-[#06281E] shadow-sm hover:bg-mint-500 active:scale-95 transition-all">
              <i data-lucide="check" class="w-4 h-4"></i>
              Подтвердить и добавить
            </button>
          </div>

          <!-- Header -->
          <div class="flex items-center justify-between px-5 pt-3 pb-2">
            <button type="button" class="close-sheet flex h-8 w-8 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-sm font-extrabold text-white">Сканирование чека</h2>
            <span class="text-xs font-extrabold text-mint-400">OCR AI</span>
          </div>
          
          <div class="px-5 py-2 space-y-4">
            <input type="file" id="receiptFileInput" accept="image/*" class="hidden">

            <!-- Merchant Card (Figma exact) -->
            <div id="receiptDropZone" class="rounded-[24px] bg-[#151D2E] border border-[#222E46] p-4 text-center space-y-2 cursor-pointer hover:border-mint-500/40 transition-all">
              <div class="flex items-center justify-between text-[11px]">
                <span class="font-mono text-mint-400">[ФНС QR КОД НАЙДЕН]</span>
                <span class="font-bold text-[#00E599] flex items-center gap-1">
                  <span class="h-2 w-2 rounded-full bg-mint-500"></span> 100%
                </span>
              </div>

              <!-- QR Icon -->
              <div class="h-10 w-10 mx-auto rounded-xl bg-mint-500/10 text-mint-400 flex items-center justify-center">
                <i data-lucide="qr-code" class="w-6 h-6"></i>
              </div>

              <div>
                <h3 id="scanMerchantName" class="text-sm font-extrabold text-white">Супермаркет «Лента»</h3>
                <p id="scanReceiptNumberAndSum" class="text-xs text-slate-400 mt-0.5">Чек №4892 · 18 920 ₽</p>
              </div>

              <div>
                <span class="px-3 py-1 rounded-full text-xs font-bold bg-[#10242B] text-mint-400 border border-[#164E43]">
                  14 позиций распознано
                </span>
              </div>
            </div>

            <!-- Items Section Header -->
            <div>
              <div class="flex items-center justify-between mb-2 text-xs px-1">
                <span class="font-extrabold text-white">Позиции из чека</span>
                <span class="text-slate-400 text-[11px]">Коснитесь, чтобы отметить</span>
              </div>

              <!-- Items List matching Figma exact -->
              <div id="scanItemsListContainer" class="space-y-2">
                <!-- Item 1 (Selected) -->
                <div class="scan-item-card p-3.5 rounded-2xl bg-[#10242B] border border-[#164E43] flex items-center justify-between cursor-pointer transition-all active:scale-[0.99]" data-selected="true" data-price="2400">
                  <div>
                    <h4 class="text-xs font-extrabold text-white">1. Стейки Рибай 2 шт</h4>
                    <p class="text-[11px] font-bold text-mint-400 mt-0.5">Только Вы и Кирилл</p>
                  </div>
                  <span class="text-sm font-black text-white">2 400 ₽</span>
                </div>

                <!-- Item 2 -->
                <div class="scan-item-card p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] flex items-center justify-between cursor-pointer transition-all active:scale-[0.99]" data-selected="false" data-price="680">
                  <div>
                    <h4 class="text-xs font-extrabold text-white">2. Угли березовые 10кг</h4>
                    <p class="text-[11px] text-slate-400 mt-0.5">На всех (4 чел)</p>
                  </div>
                  <span class="text-sm font-black text-white">680 ₽</span>
                </div>

                <!-- Item 3 -->
                <div class="scan-item-card p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] flex items-center justify-between cursor-pointer transition-all active:scale-[0.99]" data-selected="false" data-price="950">
                  <div>
                    <h4 class="text-xs font-extrabold text-white">3. Соки и минеральная вода</h4>
                    <p class="text-[11px] text-slate-400 mt-0.5">На всех (4 чел)</p>
                  </div>
                  <span class="text-sm font-black text-white">950 ₽</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- FIGMA SCREEN 5: ГОЛОСОВОЙ ВВОД РАСХОДА (Exact match to media_1788523300079.jpg) -->
        <section id="sheet-voice-input" class="sheet-content no-scrollbar max-h-[92%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          
          <!-- Top Button: Внести расход 3 950 ₽ в комнату (Figma exact amber) -->
          <div class="sticky top-0 z-20 bg-[#0E1422] border-b border-[#222E46] px-5 py-3">
            <button type="button" id="btnSubmitVoiceExpense" class="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FBBF24] py-3 text-sm font-black text-[#1E1B0E] shadow-glowAmber transition-all hover:bg-amber-400 active:scale-95">
              <i data-lucide="check" class="w-4 h-4"></i>
              Внести расход 3 950 ₽ в комнату
            </button>
          </div>

          <!-- Header -->
          <div class="flex items-center justify-between px-5 pt-3 pb-2">
            <button type="button" class="close-sheet flex h-8 w-8 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-sm font-extrabold text-white">Голосовой ввод расхода</h2>
            <span class="text-xs font-extrabold text-amber-400">Whisper AI</span>
          </div>

          <div class="px-5 py-2 space-y-4">
            <!-- Recording & Waveform Card (Figma exact) -->
            <div class="rounded-[24px] bg-[#151D2E] border border-[#222E46] p-5 text-center space-y-3">
              <h3 id="voiceRecordStatus" class="text-sm font-black text-white">Запись завершена · 0:18</h3>
              <p class="text-xs text-slate-400">Нейросеть расшифровала и сгруппировала суммы</p>

              <!-- Waveform visualizer bars (Amber) -->
              <div class="waveform-container py-1">
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
                <span class="waveform-bar"></span>
              </div>

              <!-- Glowing Mic Button -->
              <button type="button" id="btnVoiceRecordToggle" class="h-14 w-14 rounded-full bg-amber-500/20 border-2 border-amber-500 text-amber-400 flex items-center justify-center mx-auto shadow-lg hover:bg-amber-500/30 transition-all active:scale-95">
                <i data-lucide="mic" class="w-6 h-6"></i>
              </button>
            </div>

            <!-- Transcribed Text Card (Figma exact) -->
            <div class="rounded-2xl bg-[#151D2E] border border-[#222E46] p-4 text-left space-y-1.5">
              <div class="flex items-center gap-1.5 text-amber-400 text-xs font-bold">
                <i data-lucide="mic" class="w-3.5 h-3.5"></i>
                <span>Расшифровка аудио:</span>
              </div>
              <p id="voiceTranscribedQuote" class="text-xs text-slate-200 leading-relaxed italic">
                «Заправил машину на 3200 рублей, делим на меня, Кирилла и Дениса. И на заправке взял кофе и хот-доги на 750р только себе».
              </p>
            </div>

            <!-- Автоматически выделено (Figma exact) -->
            <div>
              <p class="text-xs font-bold text-slate-400 mb-2 px-1">Автоматически выделено:</p>
              <div id="voiceExtractedItemsContainer" class="space-y-2">
                <!-- Item 1 -->
                <div class="p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] flex items-center justify-between">
                  <div>
                    <h4 class="text-xs font-extrabold text-white">Бензин АИ-95</h4>
                    <p class="text-[11px] text-slate-400 mt-0.5">Делят 3 чел (по 1 066 ₽)</p>
                  </div>
                  <span class="text-sm font-black text-white">3 200 ₽</span>
                </div>

                <!-- Item 2 -->
                <div class="p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] flex items-center justify-between">
                  <div>
                    <h4 class="text-xs font-extrabold text-white">Кофе и перекус</h4>
                    <p class="text-[11px] font-semibold text-mint-400 mt-0.5">Личный расход (Вы)</p>
                  </div>
                  <span class="text-sm font-black text-white">750 ₽</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- SHEET 1: BOT / MANUAL ADD EXPENSE -->
        <section id="sheet-bot" class="sheet-content no-scrollbar max-h-[88%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <h2 class="text-lg font-black tracking-[-0.02em] text-white">Вручную в комнату</h2>
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>
          
          <div class="px-5 py-4 space-y-4">
            <div>
              <label class="text-xs font-semibold text-slate-400 block mb-1">Сумма покупки (₽)</label>
              <div class="flex items-center rounded-xl border border-[#222E46] bg-[#151D2E] px-3.5 focus-within:border-cyan-500/60 transition-all">
                <input id="addExpenseAmount" type="number" inputmode="decimal" placeholder="0" class="w-full bg-transparent py-3 text-xl font-black text-white outline-none">
                <span class="text-base font-bold text-slate-400">₽</span>
              </div>
            </div>

            <div>
              <label class="text-xs font-semibold text-slate-400 block mb-1">Категория</label>
              <select id="addExpenseCategory" class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] px-3 py-2.5 text-sm font-semibold text-white outline-none focus:border-cyan-500/60 transition-all">
                <option value="🍞 Продукты">🍞 Продукты</option>
                <option value="🚗 Транспорт">🚗 Транспорт</option>
                <option value="🏠 Жильё">🏠 Жильё</option>
                <option value="☕ Кафе">☕ Кафе</option>
                <option value="🎉 Развлечения">🎉 Развлечения</option>
                <option value="💊 Аптека">💊 Аптека</option>
                <option value="🔧 Другое">🔧 Другое</option>
              </select>
            </div>

            <div>
              <label class="text-xs font-semibold text-slate-400 block mb-1">Описание (название товара)</label>
              <input id="addExpenseDescription" type="text" placeholder="Например: Сыр, кофе, такси..." class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] px-3.5 py-2.5 text-sm text-white outline-none focus:border-cyan-500/60 transition-all">
            </div>

            <div class="flex items-center justify-between rounded-xl bg-[#151D2E] p-3 border border-[#222E46]">
              <div class="flex items-center gap-2.5">
                <span class="h-8 w-8 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center">
                  <i data-lucide="user" class="w-4 h-4"></i>
                </span>
                <div>
                  <p class="text-xs font-bold text-white">Личный расход</p>
                  <p class="text-[11px] text-slate-400">Не делить сумму на комнату</p>
                </div>
              </div>
              <input id="addExpenseIsPersonal" type="checkbox" class="h-5 w-5 rounded border-slate-600 bg-transparent text-cyan-500">
            </div>

            <button type="button" id="btnSubmitExpense" class="mt-2 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#00D29D] py-3.5 text-sm font-black text-[#06281E] shadow-glowMint transition-transform active:scale-[0.98]">
              <i data-lucide="check" class="w-4 h-4"></i> Записать покупку
            </button>
          </div>
        </section>

        <!-- SHEET 6: CREATE DEBT SHEET -->
        <section id="sheet-create-debt" class="sheet-content no-scrollbar max-h-[88%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <h2 class="text-lg font-black tracking-[-0.02em] text-white">Новый долг</h2>
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>

          <form id="formCreateDebt" class="px-5 py-4 space-y-4">
            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1.5">Направление долга</label>
              <div class="grid grid-cols-2 gap-2">
                <button type="button" id="debtDirOwedToMe" class="debt-dir-btn active py-2.5 px-3 rounded-xl border-2 border-mint-500 bg-[#10242B] text-xs font-black text-mint-400 flex items-center justify-center gap-1.5 transition-all">
                  <i data-lucide="arrow-down-left" class="w-4 h-4"></i> Мне должны
                </button>
                <button type="button" id="debtDirIOwe" class="debt-dir-btn py-2.5 px-3 rounded-xl border border-[#222E46] bg-[#151D2E] text-xs font-bold text-slate-400 flex items-center justify-center gap-1.5 transition-all">
                  <i data-lucide="arrow-up-right" class="w-4 h-4"></i> Я должен
                </button>
              </div>
            </div>

            <div>
              <label id="debtCounterpartyLabel" class="block text-xs font-bold text-slate-400 mb-1.5">Кто должен (должник)</label>
              <select id="debtMemberSelect" class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] p-3 text-sm font-semibold text-white outline-none">
                <option value="">Выберите участника комнаты...</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1.5">Сумма долга (₽)</label>
              <input type="number" id="debtAmountInput" step="0.01" min="1" placeholder="0" required class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] p-3 text-lg font-black text-white outline-none">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1.5">За что долг (описание)</label>
              <input type="text" id="debtDescriptionInput" placeholder="Например: Обед в ресторане, такси..." required class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] p-3 text-sm font-semibold text-white outline-none">
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-400 mb-1.5">Частота напоминаний</label>
              <select id="debtFrequencySelect" class="w-full rounded-xl border border-[#222E46] bg-[#151D2E] p-3 text-sm font-semibold text-white outline-none">
                <option value="none">Без напоминаний</option>
                <option value="10_min">Каждые 10 минут</option>
                <option value="30_min">Каждые 30 минут</option>
                <option value="3_times_a_day">3 раза в день</option>
                <option value="daily" selected>Ежедневно</option>
                <option value="every_3_days">Раз в 3 дня</option>
                <option value="weekly">Еженедельно</option>
              </select>
            </div>

            <button type="submit" id="btnSubmitCreateDebt" class="mt-2 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#00D29D] py-3.5 text-sm font-black text-[#06281E] shadow-glowMint transition-all hover:bg-mint-500 active:scale-95">
              <i data-lucide="check" class="w-4 h-4"></i> Зафиксировать долг
            </button>
          </form>
        </section>

        <!-- SHEET 5: ROOMS SWITCHER SHEET («МОИ КОМНАТЫ») -->
        <section id="sheet-groups" class="sheet-content no-scrollbar max-h-[85%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          <div class="sticky top-0 z-10 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <div>
              <h2 class="text-lg font-black tracking-[-0.02em] text-white">Мои комнаты</h2>
              <p class="text-xs text-slate-400">Выберите комнату или создайте новую</p>
            </div>
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>
          
          <div class="px-5 py-4 space-y-3">
            <button type="button" id="btnOpenCreateRoomSheet" class="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#00D29D] py-3 text-sm font-black text-[#06281E] shadow-glowMint hover:bg-mint-500 active:scale-95 transition-all">
              <i data-lucide="plus-circle" class="w-4 h-4"></i> Создать новую комнату
            </button>

            <div id="groupsListContainer" class="space-y-2">
              <div class="py-4 text-center text-xs text-slate-400">Загрузка комнат...</div>
            </div>
          </div>
        </section>

        <!-- FIGMA SCREEN: СОЗДАНИЕ НОВОЙ КОМНАТЫ (media_1788523338113.jpg) -->
        <section id="sheet-create-room" class="sheet-content no-scrollbar max-h-[94%] w-full overflow-y-auto rounded-t-[32px] bg-[#0E1422] pb-[max(24px,env(safe-area-inset-bottom))] shadow-sheet transform translate-y-full transition-transform duration-250 ease-out hidden">
          
          <!-- Sticky Header -->
          <div class="sticky top-0 z-20 flex items-center justify-between border-b border-[#222E46] bg-[#0E1422] px-5 py-4">
            <button type="button" class="close-sheet flex h-9 w-9 items-center justify-center rounded-full bg-[#151D2E] text-slate-400 hover:text-white transition-colors">
              <i data-lucide="arrow-left" class="w-4 h-4"></i>
            </button>
            <h2 class="text-base font-extrabold text-white">Новая комната</h2>
            <div class="w-9"></div>
          </div>

          <form id="formCreateRoomFigma" class="px-5 py-4 space-y-4">
            <!-- 1. Формат сбора расходов -->
            <div>
              <label class="block text-xs font-semibold text-slate-400 mb-2">Формат сбора расходов</label>
              <div class="grid grid-cols-2 gap-3">
                <!-- Option 1: Разовый чек -->
                <button type="button" id="btnFormatOneTime" class="room-format-btn p-3.5 rounded-2xl bg-[#151D2E] border border-[#222E46] text-left transition-all active:scale-[0.98]" data-format="one_time">
                  <div class="flex items-center gap-2 mb-2 text-slate-400">
                    <i data-lucide="receipt" class="w-5 h-5"></i>
                  </div>
                  <h4 class="text-sm font-extrabold text-white">Разовый чек</h4>
                  <p class="text-[11px] text-slate-400 mt-0.5">Ужин в ресторане</p>
                </button>

                <!-- Option 2: Длительная (Selected in mockup) -->
                <button type="button" id="btnFormatLongTerm" class="room-format-btn p-3.5 rounded-2xl bg-[#0C2B24] border-2 border-[#00D29D] text-left shadow-glowMint transition-all active:scale-[0.98]" data-format="long_term">
                  <div class="flex items-center gap-2 mb-2 text-[#00E599]">
                    <i data-lucide="folder" class="w-5 h-5"></i>
                  </div>
                  <h4 class="text-sm font-extrabold text-[#00E599]">Длительная</h4>
                  <p class="text-[11px] text-mint-300/80 mt-0.5">Поездка, отпуск, быт</p>
                </button>
              </div>
            </div>

            <!-- 2. Название комнаты -->
            <div>
              <label class="block text-xs font-semibold text-slate-400 mb-2">Название комнаты</label>
              <div class="flex items-center justify-between rounded-2xl border border-[#222E46] bg-[#151D2E] px-4 py-3.5 focus-within:border-mint-500/60 transition-all">
                <input type="text" id="createRoomNameInput" value="Дача & Выходные в августе" placeholder="Название комнаты" class="w-full bg-transparent text-sm font-bold text-white placeholder:text-slate-500 outline-none">
                <i data-lucide="pencil" class="w-4 h-4 text-slate-400 shrink-0 ml-2"></i>
              </div>
            </div>

            <!-- 3. Валюта и Взаиморасчет (Figma exact cards) -->
            <div class="grid grid-cols-2 gap-3">
              <!-- Валюта -->
              <div id="roomCurrencySelectorCard" class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-3.5 cursor-pointer hover:border-slate-500/50 transition-all">
                <p class="text-xs text-slate-400">Валюта</p>
                <div class="flex items-center justify-between mt-1">
                  <span id="createRoomCurrencyDisplay" class="text-sm font-black text-white">RUB ( ₽ )</span>
                  <i data-lucide="chevron-down" class="w-3.5 h-3.5 text-slate-400"></i>
                </div>
              </div>

              <!-- Взаиморасчет -->
              <div id="roomSettlementStrategyCard" class="rounded-2xl border border-[#222E46] bg-[#151D2E] p-3.5 cursor-pointer hover:border-mint-500/50 transition-all">
                <p class="text-xs text-slate-400">Взаиморасчет</p>
                <div class="flex items-center justify-between mt-1">
                  <span id="createRoomStrategyDisplay" class="text-sm font-black text-[#00E599]">Мин. переводов</span>
                  <i data-lucide="arrow-left-right" class="w-3.5 h-3.5 text-[#00E599]"></i>
                </div>
              </div>
            </div>

            <!-- Участники комнаты -->
            <div>
              <div class="flex items-center justify-between mb-2">
                <span id="createRoomMembersCountHeader" class="text-sm font-extrabold text-white">Участники (1)</span>
                <button type="button" id="btnAddParticipantFromContacts" class="text-xs font-bold text-[#00D29D] hover:underline transition-all">
                  + Из контактов
                </button>
              </div>

              <!-- Список заполняется только приглашёнными участниками. -->
              <div id="createRoomParticipantsList" class="rounded-2xl border border-[#222E46] bg-[#151D2E] divide-y divide-[#222E46]/60 overflow-hidden">
                <!-- Creator (You) -->
                <div class="flex items-center justify-between p-3.5">
                  <div class="flex items-center gap-3">
                    <span class="flex h-9 w-9 items-center justify-center rounded-full bg-[#00D29D] text-[#06281E] font-black text-xs">
                      Я
                    </span>
                    <span class="text-xs font-bold text-white">Вы</span>
                  </div>
                  <span class="flex h-5 w-5 items-center justify-center rounded-full bg-[#00D29D] text-[#06281E]">
                    <i data-lucide="check" class="w-3.5 h-3.5 stroke-[3]"></i>
                  </span>
                </div>

              </div>
            </div>

            <!-- Sticky CTA Button (Figma exact mint) -->
            <div class="pt-2">
              <button type="submit" id="btnSubmitCreateRoomFigma" class="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#00D29D] py-3.5 text-sm font-black text-[#06281E] shadow-glowMint hover:bg-mint-500 active:scale-[0.98] transition-all">
                Создать и пригласить по ссылке →
              </button>
            </div>
          </form>
        </section>

      </div>

      <!-- TOAST NOTIFICATION CONTAINER -->
      <div id="toastContainer" class="pointer-events-none fixed top-4 inset-x-0 z-50 flex flex-col items-center gap-2 px-4"></div>

    </div>
  </div>

  <script src="app.js"></script>
</body>
</html>"""

with open(os.path.join(WEBAPP_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_html)
print("Wrote dark theme index.html successfully.")
