/**
 * main.js — CivicQuest frontend controller.
 *
 * Manages game state, API communication, UI rendering,
 * accessibility announcements, and event handling.
 */

// ── Constants ─────────────────────────────────────────────────────────────────

const LANGS = [
  { code: 'en', label: 'English' }, { code: 'hi', label: 'Hindi' },
  { code: 'gu', label: 'ગુજ.' },  { code: 'ta', label: 'தமிழ்' },
  { code: 'te', label: 'తెలుగు' }, { code: 'mr', label: 'मराठी' },
  { code: 'bn', label: 'বাংলা' },  { code: 'kn', label: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'മലയ' },    { code: 'pa', label: 'ਪੰਜਾਬੀ' },
];

const ALL_BADGES = [
  { emoji: '📋', name: 'Registered Citizen' },
  { emoji: '🗺️', name: 'Constituency Scholar' },
  { emoji: '📅', name: 'Election Analyst' },
  { emoji: '🗳️', name: 'Polling Expert' },
  { emoji: '🏆', name: 'Democracy Champion' },
];

const MAX_XP = 1000;

// ── State ─────────────────────────────────────────────────────────────────────

let sessionId = null;
let gameState = null;
let map = null;
let currentLang = 'en';

// ── Initialization ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  buildLangGrid();

  // Register all event listeners (no inline handlers)
  document.getElementById('setup-form').addEventListener('submit', startGame);
  document.getElementById('send-btn').addEventListener('click', () => sendMessage());
  document.getElementById('next-quest-btn').addEventListener('click', nextQuest);
  document.getElementById('booth-search-btn').addEventListener('click', findBooth);
  document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });
});

// ── Screen Reader Announcer ───────────────────────────────────────────────────

/**
 * Announce text to screen readers via the live region.
 * @param {string} text - The message to announce.
 */
function announce(text) {
  const announcer = document.getElementById('sr-announcer');
  if (announcer) {
    announcer.textContent = '';
    // Brief delay ensures screen readers detect the content change
    setTimeout(() => { announcer.textContent = text; }, 100);
  }
}

// ── HTML Sanitizer ────────────────────────────────────────────────────────────

/**
 * Sanitize a string to prevent XSS when used with innerHTML.
 * Strips <script> tags, event handlers, and dangerous elements.
 * @param {string} raw - Raw string from API response.
 * @returns {string} Sanitized string safe for innerHTML.
 */
function sanitizeHTML(raw) {
  if (typeof raw !== 'string') return '';

  // Create a temporary element and set as text first
  const temp = document.createElement('div');
  temp.textContent = raw;
  let safe = temp.innerHTML;

  // Convert newlines to <br> for readability
  safe = safe.replace(/\n/g, '<br>');

  return safe;
}

// ── Start Game ────────────────────────────────────────────────────────────────

/**
 * Handle the game start form submission.
 * @param {Event} e - The form submit event.
 */
async function startGame(e) {
  e.preventDefault();
  const btn = document.getElementById('start-btn');
  const name = document.getElementById('player-name').value.trim();
  const state = document.getElementById('player-state').value;
  const lang = document.getElementById('player-lang').value;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Loading…';
  currentLang = lang;

  const res = await post('/api/start', { name, state, language: lang });
  if (!res) {
    btn.disabled = false;
    btn.textContent = '⚔️ Begin Adventure';
    return;
  }

  sessionId = res.session_id;
  gameState = res.game_state;

  document.getElementById('welcome-screen').classList.add('hidden');
  document.getElementById('game-area').classList.add('visible');
  document.getElementById('hud').classList.remove('hud-hidden');

  // Update <html lang> to match selected language
  document.documentElement.lang = lang;

  updateHUD();
  buildProgressDots();
  buildBadgesGrid();
  initMap();
  activateLang(lang);
  await loadScene();

  // Focus management: move focus to the quest title for screen readers
  const questTitle = document.getElementById('quest-title');
  if (questTitle) questTitle.focus();

  announce(`Game started. Welcome ${name}. Your first quest is ready.`);
}

// ── Load Scene Narration ──────────────────────────────────────────────────────

/**
 * Fetch and display the current quest scene.
 */
async function loadScene() {
  addMsg('guide', '<span class="spinner"></span> Desh is preparing your quest…');
  const res = await post('/api/scene', { session_id: sessionId });
  clearWindow();

  if (!res) {
    addMsg('guide', 'Unable to load quest. Please try again.');
    return;
  }

  if (res.type === 'game_over') {
    addMsg('guide', res.message);
    announce('Congratulations! You have completed all quests.');
    return;
  }

  document.getElementById('quest-title').textContent = res.quest_title;
  document.getElementById('quest-subtitle').textContent = res.quest_subtitle;
  document.getElementById('quest-icon').textContent = res.badge_emoji;

  addMsg('guide', res.narration);
  buildQuickQs(res.suggested_questions);
  document.getElementById('complete-banner').classList.remove('show');

  announce(`Quest loaded: ${res.quest_title}`);
}

// ── Send Message ──────────────────────────────────────────────────────────────

/**
 * Send a player message to the game engine.
 * @param {string} [text] - Optional preset message text (from quick questions).
 */
async function sendMessage(text) {
  const input = document.getElementById('chat-input');
  const msg = text || input.value.trim();
  if (!msg) return;

  input.value = '';
  clearQuickQs();
  addMsg('player', msg);

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;
  addMsg('guide', '<span class="spinner"></span> Desh is thinking…', 'typing-msg');

  const res = await post('/api/answer', { session_id: sessionId, input: msg });
  removeMsg('typing-msg');
  sendBtn.disabled = false;

  if (!res) {
    addMsg('guide', 'Unable to get response. Please try again.');
    return;
  }

  addMsg('guide', res.response);
  if (res.xp_gained > 0) {
    addXpToast(`+${res.xp_gained} XP`);
    announce(`You earned ${res.xp_gained} experience points!`);
  }

  gameState = res.game_state;
  updateHUD();

  // Show "quest complete" button after enough interaction
  if (res.quest_progressed) showCompletePrompt(gameState);
}

// ── Next Quest ────────────────────────────────────────────────────────────────

/**
 * Advance to the next quest when the player is ready.
 */
async function nextQuest() {
  const res = await post('/api/next_quest', { session_id: sessionId });

  if (!res) {
    addMsg('guide', 'Unable to advance quest. Please try again.');
    return;
  }

  if (res.type === 'game_over') {
    clearWindow();
    addMsg('guide', res.message);
    document.getElementById('complete-banner').classList.remove('show');
    document.getElementById('quest-title').textContent = '🏆 You are a Democracy Champion!';
    announce('Congratulations! You have completed all quests and are now a Democracy Champion!');
    return;
  }

  gameState = res.game_state;
  updateHUD();
  buildProgressDots();
  buildBadgesGrid();
  await loadScene();

  announce(`Badge earned! Moving to quest ${gameState.quest_index + 1} of ${gameState.total_quests}.`);
}

// ── Booth Finder ──────────────────────────────────────────────────────────────

/**
 * Search for polling booths using Google Maps Places API.
 */
function findBooth() {
  if (!map) return;
  const addr = document.getElementById('booth-address').value.trim();
  if (!addr) return;

  const query = `polling booth ${addr} ${gameState?.state_name || ''} India`;
  if (window.google) {
    const service = new google.maps.places.PlacesService(map);
    service.textSearch({ query }, (results, status) => {
      if (status === google.maps.places.PlacesServiceStatus.OK && results[0]) {
        map.setCenter(results[0].geometry.location);
        map.setZoom(14);
        new google.maps.Marker({
          map,
          position: results[0].geometry.location,
          title: results[0].name,
        });
        announce(`Found polling booth: ${results[0].name}`);
      } else {
        announce('No polling booths found for that location.');
      }
    });
  }
}

/**
 * Initialize the Google Maps instance.
 */
function initMap() {
  if (!window.google) return;
  map = new google.maps.Map(document.getElementById('booth-map'), {
    center: { lat: 23.0225, lng: 72.5714 },
    zoom: 11,
    styles: [
      { elementType: 'geometry', stylers: [{ color: '#1d2c4d' }] },
      { elementType: 'labels.text.fill', stylers: [{ color: '#8ec3b9' }] },
    ],
  });
}

// ── UI Helpers ────────────────────────────────────────────────────────────────

/**
 * Add a message bubble to the chat window.
 * @param {string} type - 'guide' or 'player'.
 * @param {string} content - Message content.
 * @param {string} [id] - Optional element ID for later removal.
 */
function addMsg(type, content, id) {
  const win = document.getElementById('chat-window');
  const div = document.createElement('div');
  div.className = `msg msg-${type}`;
  if (id) div.id = id;

  if (type === 'guide') {
    // Sanitize AI responses to prevent XSS
    div.innerHTML = `<strong>⚔ Desh</strong>${sanitizeHTML(content)}`;
  } else {
    div.textContent = content;
  }

  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
}

/**
 * Remove a message element by ID.
 * @param {string} id - The element ID to remove.
 */
function removeMsg(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/**
 * Clear all messages from the chat window.
 */
function clearWindow() {
  document.getElementById('chat-window').innerHTML = '';
}

/**
 * Display an XP gain toast notification.
 * @param {string} text - The toast text (e.g. "+25 XP").
 */
function addXpToast(text) {
  const win = document.getElementById('chat-window');
  const div = document.createElement('div');
  div.className = 'xp-toast';
  div.textContent = text;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  setTimeout(() => div.remove(), 3000);
}

/**
 * Update the heads-up display with current game state.
 */
function updateHUD() {
  if (!gameState) return;
  document.getElementById('hud-name').textContent = gameState.player_name;
  document.getElementById('hud-xp').textContent = gameState.total_xp;
  document.getElementById('hud-quest').textContent =
    `Quest ${gameState.quest_index + 1}/${gameState.total_quests}`;

  const xpPct = Math.min(100, (gameState.total_xp / MAX_XP) * 100);
  document.getElementById('xp-bar').style.width = xpPct + '%';

  // Update ARIA attributes for accessibility
  const progressBar = document.getElementById('xp-progress-bar');
  if (progressBar) {
    progressBar.setAttribute('aria-valuenow', gameState.total_xp);
    progressBar.setAttribute('aria-valuetext', `${gameState.total_xp} of ${MAX_XP} experience points`);
  }
}

/**
 * Build the quest progress dots indicator.
 */
function buildProgressDots() {
  if (!gameState) return;
  const wrap = document.getElementById('progress-dots');
  const frag = document.createDocumentFragment();
  for (let i = 0; i < gameState.total_quests; i++) {
    const d = document.createElement('div');
    d.className = 'dot' + (
      i < gameState.quest_index ? ' done' :
      i === gameState.quest_index ? ' active' : ''
    );
    d.setAttribute('aria-label', `Quest ${i + 1}: ${i < gameState.quest_index ? 'completed' : i === gameState.quest_index ? 'current' : 'locked'}`);
    frag.appendChild(d);
  }
  wrap.innerHTML = '';
  wrap.appendChild(frag);
}

/**
 * Build the badges display grid.
 */
function buildBadgesGrid() {
  const grid = document.getElementById('badges-grid');
  const frag = document.createDocumentFragment();
  const earned = (gameState?.badges || []).map(b => b.name);
  ALL_BADGES.forEach(b => {
    const chip = document.createElement('div');
    const isEarned = earned.includes(b.name);
    chip.className = 'badge-chip' + (isEarned ? '' : ' locked');
    chip.setAttribute('aria-label', `${b.name}: ${isEarned ? 'earned' : 'locked'}`);
    chip.innerHTML = `<span role="img" aria-hidden="true">${b.emoji}</span><span>${b.name}</span>`;
    frag.appendChild(chip);
  });
  grid.innerHTML = '';
  grid.appendChild(frag);
}

/**
 * Build the suggested quick-question buttons.
 * @param {string[]} questions - Array of suggested question strings.
 */
function buildQuickQs(questions) {
  const wrap = document.getElementById('quick-qs');
  wrap.innerHTML = '';
  (questions || []).slice(0, 4).forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'quick-q';
    btn.textContent = q;
    btn.addEventListener('click', () => sendMessage(q));
    wrap.appendChild(btn);
  });
}

/**
 * Clear all suggested question buttons.
 */
function clearQuickQs() {
  document.getElementById('quick-qs').innerHTML = '';
}

/**
 * Show the quest completion banner.
 * @param {Object} gs - Current game state.
 */
function showCompletePrompt(gs) {
  const banner = document.getElementById('complete-banner');
  const quest = gs ? ALL_BADGES[gs.quest_index] : null;
  if (quest) {
    document.getElementById('banner-badge-text').textContent =
      `${quest.emoji} Quest Complete — ${quest.name}`;
    document.getElementById('banner-msg').textContent =
      'You have earned a new badge! Ready for the next quest?';
  }
  banner.classList.add('show');
  announce('Quest complete! You earned a new badge.');
}

/**
 * Build the language selection grid.
 */
function buildLangGrid() {
  const grid = document.getElementById('lang-grid');
  LANGS.forEach(l => {
    const btn = document.createElement('button');
    btn.className = 'lang-btn' + (l.code === currentLang ? ' active' : '');
    btn.dataset.code = l.code;
    btn.textContent = l.label;
    btn.setAttribute('aria-label', `Switch language to ${l.label}`);
    btn.addEventListener('click', () => activateLang(l.code));
    grid.appendChild(btn);
  });
}

/**
 * Activate a language and update the UI.
 * @param {string} code - Language code (e.g. 'en', 'hi').
 */
function activateLang(code) {
  currentLang = code;
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.code === code);
  });
  if (gameState) gameState.language = code;

  // Update the html lang attribute for accessibility
  document.documentElement.lang = code;
}

// ── API Helper ────────────────────────────────────────────────────────────────

/**
 * POST JSON to an API endpoint with error handling.
 * @param {string} url - The API endpoint URL.
 * @param {Object} body - The request body.
 * @returns {Object|null} Parsed JSON response, or null on failure.
 */
async function post(url, body) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const errorMsg = errorData.error || `Request failed (${res.status})`;
      logger.warn(`API error on ${url}: ${errorMsg}`);
      showErrorToast(errorMsg);
      return null;
    }

    return await res.json();
  } catch (err) {
    logger.error(`Network error on ${url}:`, err);
    showErrorToast('Network error — please check your connection and try again.');
    return null;
  }
}

// ── Error Toast ───────────────────────────────────────────────────────────────

/**
 * Display a user-visible error toast notification.
 * @param {string} message - Error message to display.
 */
function showErrorToast(message) {
  const win = document.getElementById('chat-window');
  if (!win) return;

  const toast = document.createElement('div');
  toast.className = 'error-toast';
  toast.setAttribute('role', 'alert');
  toast.textContent = `⚠ ${message}`;
  win.appendChild(toast);
  win.scrollTop = win.scrollHeight;
  setTimeout(() => toast.remove(), 5000);
}

// ── Simple Logger ─────────────────────────────────────────────────────────────

const logger = {
  info: (...args) => console.log('[CivicQuest]', ...args),
  warn: (...args) => console.warn('[CivicQuest]', ...args),
  error: (...args) => console.error('[CivicQuest]', ...args),
};
