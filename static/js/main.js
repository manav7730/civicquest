// ── State ─────────────────────────────────────────────────────────────────────
const LANGS = [
  { code:'en', label:'English' }, { code:'hi', label:'Hindi' },
  { code:'gu', label:'ગુજ.'    }, { code:'ta', label:'தமிழ்'  },
  { code:'te', label:'తెలుగు'  }, { code:'mr', label:'मराठी' },
  { code:'bn', label:'বাংলা'  }, { code:'kn', label:'ಕನ್ನಡ' },
  { code:'ml', label:'മലയ'    }, { code:'pa', label:'ਪੰਜਾਬੀ'  },
];
const ALL_BADGES = [
  { emoji:'📋', name:'Registered Citizen'   },
  { emoji:'🗺️', name:'Constituency Scholar' },
  { emoji:'📅', name:'Election Analyst'     },
  { emoji:'🗳️', name:'Polling Expert'       },
  { emoji:'🏆', name:'Democracy Champion'   },
];
const MAX_XP = 1000;

let sessionId    = null;
let gameState    = null;
let map          = null;
let currentLang  = 'en';

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildLangGrid();
  document.getElementById('chat-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
  });
});

// ── Start game ────────────────────────────────────────────────────────────────
async function startGame(e) {
  e.preventDefault();
  const btn    = document.getElementById('start-btn');
  const name   = document.getElementById('player-name').value.trim();
  const state  = document.getElementById('player-state').value;
  const lang   = document.getElementById('player-lang').value;

  btn.disabled   = true;
  btn.innerHTML  = '<span class="spinner"></span> Loading…';
  currentLang    = lang;

  const res  = await post('/api/start', { name, state, language: lang });
  sessionId  = res.session_id;
  gameState  = res.game_state;

  document.getElementById('welcome-screen').style.display = 'none';
  document.getElementById('game-area').classList.add('visible');
  document.getElementById('hud').style.display = 'flex';

  updateHUD();
  buildProgressDots();
  buildBadgesGrid();
  initMap();
  activateLang(lang);
  await loadScene();
}

// ── Load scene narration ───────────────────────────────────────────────────────
async function loadScene() {
  addMsg('guide', '<span class="spinner"></span> Desh is preparing your quest…');
  const res = await post('/api/scene', { session_id: sessionId });
  clearWindow();

  if (res.type === 'game_over') {
    addMsg('guide', res.message);
    return;
  }

  document.getElementById('quest-title').textContent   = res.quest_title;
  document.getElementById('quest-subtitle').textContent = res.quest_subtitle;
  document.getElementById('quest-icon').textContent     = res.badge_emoji;

  addMsg('guide', res.narration);
  buildQuickQs(res.suggested_questions);
  document.getElementById('complete-banner').classList.remove('show');
}

// ── Send message ──────────────────────────────────────────────────────────────
async function sendMessage(text) {
  const input = document.getElementById('chat-input');
  const msg   = text || input.value.trim();
  if (!msg) return;

  input.value = '';
  clearQuickQs();
  addMsg('player', msg);

  const sendBtn  = document.getElementById('send-btn');
  sendBtn.disabled = true;
  addMsg('guide', '<span class="spinner"></span> Desh is thinking…', 'typing-msg');

  const res = await post('/api/answer', { session_id: sessionId, input: msg });
  removeMsg('typing-msg');
  sendBtn.disabled = false;

  addMsg('guide', res.response);
  if (res.xp_gained > 0) addXpToast(`+${res.xp_gained} XP`);

  gameState = res.game_state;
  updateHUD();

  // Show "quest complete" button after enough interaction
  if (res.quest_progressed) showCompletePrompt(gameState);
}

// ── Next quest ────────────────────────────────────────────────────────────────
async function nextQuest() {
  const res = await post('/api/next_quest', { session_id: sessionId });

  if (res.type === 'game_over') {
    clearWindow();
    addMsg('guide', res.message);
    document.getElementById('complete-banner').classList.remove('show');
    document.getElementById('quest-title').textContent = '🏆 You are a Democracy Champion!';
    return;
  }

  gameState = res.game_state;
  updateHUD();
  buildProgressDots();
  buildBadgesGrid();
  await loadScene();
}

// ── Booth finder ──────────────────────────────────────────────────────────────
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
        new google.maps.Marker({ map, position: results[0].geometry.location, title: results[0].name });
      }
    });
  }
}

function initMap() {
  if (!window.google) return;
  map = new google.maps.Map(document.getElementById('booth-map'), {
    center: { lat: 23.0225, lng: 72.5714 },
    zoom: 11,
    styles: [{ elementType:'geometry', stylers:[{ color:'#1d2c4d' }] },
             { elementType:'labels.text.fill', stylers:[{ color:'#8ec3b9' }] }],
  });
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function addMsg(type, html, id) {
  const win  = document.getElementById('chat-window');
  const div  = document.createElement('div');
  div.className = `msg msg-${type}`;
  if (id) div.id = id;
  if (type === 'guide') div.innerHTML = `<strong>⚔ Desh</strong>${html}`;
  else div.textContent = html;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
}
function removeMsg(id) { document.getElementById(id)?.remove(); }
function clearWindow() { document.getElementById('chat-window').innerHTML = ''; }
function addXpToast(text) {
  const win  = document.getElementById('chat-window');
  const div  = document.createElement('div');
  div.className = 'xp-toast';
  div.textContent = text;
  win.appendChild(div);
  win.scrollTop = win.scrollHeight;
  setTimeout(() => div.remove(), 3000);
}

function updateHUD() {
  if (!gameState) return;
  document.getElementById('hud-name').textContent  = gameState.player_name;
  document.getElementById('hud-xp').textContent    = gameState.total_xp;
  document.getElementById('hud-quest').textContent = `Quest ${gameState.quest_index + 1}/${gameState.total_quests}`;
  document.getElementById('xp-bar').style.width    = Math.min(100, (gameState.total_xp / MAX_XP) * 100) + '%';
}

function buildProgressDots() {
  if (!gameState) return;
  const wrap = document.getElementById('progress-dots');
  const frag = document.createDocumentFragment();
  for (let i = 0; i < gameState.total_quests; i++) {
    const d = document.createElement('div');
    d.className = 'dot' + (i < gameState.quest_index ? ' done' : i === gameState.quest_index ? ' active' : '');
    frag.appendChild(d);
  }
  wrap.innerHTML = '';
  wrap.appendChild(frag);
}

function buildBadgesGrid() {
  const grid = document.getElementById('badges-grid');
  const frag = document.createDocumentFragment();
  const earned = (gameState?.badges || []).map(b => b.name);
  ALL_BADGES.forEach(b => {
    const chip = document.createElement('div');
    chip.className = 'badge-chip' + (earned.includes(b.name) ? '' : ' locked');
    chip.innerHTML = `<span style="font-size:14px" role="img" aria-label="${b.name}">${b.emoji}</span><span>${b.name}</span>`;
    frag.appendChild(chip);
  });
  grid.innerHTML = '';
  grid.appendChild(frag);
}

function buildQuickQs(questions) {
  const wrap = document.getElementById('quick-qs');
  wrap.innerHTML = '';
  (questions || []).slice(0, 4).forEach(q => {
    const btn = document.createElement('button');
    btn.className   = 'quick-q';
    btn.textContent = q;
    btn.onclick     = () => sendMessage(q);
    wrap.appendChild(btn);
  });
}
function clearQuickQs() { document.getElementById('quick-qs').innerHTML = ''; }

function showCompletePrompt(gs) {
  const banner = document.getElementById('complete-banner');
  const quest  = gs ? ALL_BADGES[gs.quest_index] : null;
  if (quest) {
    document.getElementById('banner-badge-text').textContent = `${quest.emoji} Quest Complete — ${quest.name}`;
    document.getElementById('banner-msg').textContent = 'You have earned a new badge! Ready for the next quest?';
  }
  banner.classList.add('show');
}

function buildLangGrid() {
  const grid = document.getElementById('lang-grid');
  LANGS.forEach(l => {
    const btn = document.createElement('button');
    btn.className   = 'lang-btn' + (l.code === currentLang ? ' active' : '');
    btn.dataset.code = l.code;
    btn.textContent  = l.label;
    btn.onclick      = () => activateLang(l.code);
    grid.appendChild(btn);
  });
}
function activateLang(code) {
  currentLang = code;
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.code === code);
  });
  if (gameState) gameState.language = code;
}

// ── API helper ────────────────────────────────────────────────────────────────
async function post(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}
