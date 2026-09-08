# builder_css.py
import os

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")

css_content = """/* СберСплит Mini App — Dark FinTech Theme from Figma References */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
  --bg-app: #0B0F19;
  --bg-shell: #0E1422;
  --bg-card: #151D2E;
  --border-card: #222E46;
  --color-mint: #00E599;
  --color-mint-btn: #00D29D;
  --color-cyan: #00A3FF;
  --color-amber: #FBBF24;
  --color-indigo: #5B50E6;
}

html, body {
  height: 100%;
  margin: 0;
  padding: 0;
  background-color: #0B0F19;
  color: #F8FAFC;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

/* Hide scrollbar */
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Screen panes */
.screen-pane {
  animation: fadeIn 0.18s cubic-bezier(0.23, 1, 0.32, 1) forwards;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Bottom Sheet Animations */
#sheetOverlay {
  transition: opacity 0.22s cubic-bezier(0.23, 1, 0.32, 1);
  background-color: rgba(0, 0, 0, 0.75);
}
#sheetOverlay.active {
  display: flex !important;
  opacity: 1 !important;
}

.sheet-content {
  transition: transform 0.26s cubic-bezier(0.23, 1, 0.32, 1);
  background-color: #0E1422 !important;
  border-top: 1px solid #222E46 !important;
}
.sheet-content.active {
  display: block !important;
  transform: translateY(0%) !important;
}

/* Toast styling */
.toast-msg {
  animation: toastIn 0.25s cubic-bezier(0.23, 1, 0.32, 1) forwards;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

@keyframes toastIn {
  from { opacity: 0; transform: translateY(-12px); }
  to { opacity: 1; transform: translateY(0); }
}

.toast-msg.hiding {
  opacity: 0;
  transform: translateY(-8px);
  transition: all 0.2s ease-in;
}

/* Category Filter button active */
.cat-pill.active {
  background-color: #00D29D !important;
  color: #06281E !important;
  font-weight: 800 !important;
}

/* Voice Waveform animation */
.waveform-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 40px;
}
.waveform-bar {
  width: 4px;
  background-color: #FBBF24;
  border-radius: 9999px;
  animation: waveAnim 1s ease-in-out infinite alternate;
}
.waveform-bar:nth-child(1) { height: 12px; animation-delay: 0.1s; }
.waveform-bar:nth-child(2) { height: 24px; animation-delay: 0.3s; }
.waveform-bar:nth-child(3) { height: 36px; animation-delay: 0.15s; }
.waveform-bar:nth-child(4) { height: 28px; animation-delay: 0.4s; }
.waveform-bar:nth-child(5) { height: 38px; animation-delay: 0.2s; }
.waveform-bar:nth-child(6) { height: 20px; animation-delay: 0.35s; }
.waveform-bar:nth-child(7) { height: 32px; animation-delay: 0.05s; }
.waveform-bar:nth-child(8) { height: 14px; animation-delay: 0.25s; }

@keyframes waveAnim {
  0% { transform: scaleY(0.3); opacity: 0.6; }
  100% { transform: scaleY(1); opacity: 1; }
}

/* Glowing mic pulse */
@keyframes micPulse {
  0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
  70% { box-shadow: 0 0 0 16px rgba(245, 158, 11, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}
.mic-recording {
  animation: micPulse 1.5s infinite;
}

canvas {
  touch-action: none;
}
"""

with open(os.path.join(WEBAPP_DIR, "style.css"), "w", encoding="utf-8") as f:
    f.write(css_content)
print("Wrote style.css successfully.")
