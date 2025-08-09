console.log('Chatbot script loaded!');

// ====== STATE MANAGEMENT ======
const LS_KEY = 'mediAI_conversations';
let current = { id: Date.now(), ts: Date.now(), messages: [] };
let botReplyCount = 0;
let firstOpen = true;
let currentLanguage = 'en'; // 'en' or 'fr'

// ====== TRANSLATIONS ======
const translations = {
  greetings: {
    en: "Hi there! I'm your virtual doc. How can I assist you today?",
    fr: "Bonjour ! Je suis votre assistant médical. Comment puis-je vous aider ?"
  },
  welcomeBack: {
    en: "👋 Welcome back! Here's your previous conversation.",
    fr: "👋 Bon retour ! Voici votre conversation précédente."
  },
  newChat: {
    en: "👋 New chat started",
    fr: "👋 Nouvelle conversation"
  },
  thinking: {
    en: "Thinking",
    fr: "Réflexion"
  },
  inputPlaceholder: {
    en: "Type your message...",
    fr: "Tapez votre message..."
  },
  wsConnected: {
    en: "Connected to real-time chat",
    fr: "Connecté au chat en temps réel"
  },
  wsDisconnected: {
    en: "Disconnected from real-time chat",
    fr: "Déconnecté du chat en temps réel"
  }
};

// ====== DOM ELEMENTS ======
const launcher = document.getElementById('chatbot-launcher');
const panel = document.getElementById('chatbot-panel');
const form = document.getElementById('chatbot-input-row');
const input = document.getElementById('chatbot-input');
const messagesEl = document.getElementById('chatbot-messages');
const newBtn = document.getElementById('new-chat');
const histBtn = document.getElementById('chat-history-toggle');
const histDrawer = document.getElementById('chatbot-history');
const listEl = document.getElementById('history-list');
const languageToggle = document.getElementById('language-toggle');
const statusIndicator = document.createElement('div');
statusIndicator.className = 'chat-status';
panel.insertBefore(statusIndicator, messagesEl);

console.log("Launcher exists:", !!launcher);
console.log("Panel exists:", !!panel);

// ====== UTILITY FUNCTIONS ======
const loadConvos = () => JSON.parse(localStorage.getItem(LS_KEY) || '[]');
const saveConvos = (c) => localStorage.setItem(LS_KEY, JSON.stringify(c));

function scrollIfNeeded() {
  if (botReplyCount > 3) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

function updateUILanguage() {
  input.placeholder = translations.inputPlaceholder[currentLanguage];
  languageToggle.textContent = currentLanguage === 'en' ? '🌐 FR' : '🌐 EN';
}

function addBubble(text, who) {
  const wrapper = document.createElement('div');
  wrapper.className = `chat-line ${who}`;
  const emoji = document.createElement('div');
  emoji.className = 'chat-emoji';
  emoji.textContent = who === 'user' ? '🧑‍💻' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = text;

  if (who === 'user') {
    wrapper.append(bubble, emoji);
  } else {
    wrapper.append(emoji, bubble);
  }

  messagesEl.appendChild(wrapper);
  scrollIfNeeded();
  current.messages.push({ role: who, text });
  return wrapper;
}

function persistCurrent() {
  if (!current.messages.length) return;
  const all = loadConvos().filter(c => c.id !== current.id);
  all.push(current);
  saveConvos(all);
}

function showGreeting() {
  addBubble(translations.greetings[currentLanguage], 'bot');
}

function showWelcomeBack() {
  addBubble(translations.welcomeBack[currentLanguage], 'bot');
}

function startNewChat() {
  current = { id: Date.now(), ts: Date.now(), messages: [] };
  botReplyCount = 0;
  messagesEl.innerHTML = '';
  botReply();
}

function refreshHistory() {
  listEl.innerHTML = '';
  loadConvos().forEach(c => {
    const li = document.createElement('li');
    li.textContent = new Date(c.ts).toLocaleString();
    li.onclick = () => loadChat(c.id);
    listEl.appendChild(li);
  });
}

function loadChat(id) {
  persistCurrent();
  const convo = loadConvos().find(c => c.id === id);
  if (!convo) return;

  current = convo;
  botReplyCount = convo.messages.filter(m => m.role === 'bot').length;
  messagesEl.innerHTML = '';
  convo.messages.forEach(m => addBubble(m.text, m.role));
  histDrawer.hidden = true;
  panel.style.display = 'flex';
  input.focus();
  firstOpen = false;
  showWelcomeBack();
}

function botFallback(t) {
  const q = t.toLowerCase();
  if (currentLanguage === 'fr') {
    if (/(salut|bonjour)/.test(q)) return "👋 Bonjour ! Comment puis-je vous aider ?";
    if (/ça va/.test(q)) return "Je suis un bot, mais je vais bien ! Et vous ?";
    if (/aide/.test(q)) return "Bien sûr ! De quoi avez-vous besoin ?";
    if (/merci/.test(q)) return "De rien ! 😊";
    if (/au revoir/.test(q)) return "Au revoir !";
    return "😕 Désolé, je n'ai pas compris. Pouvez-vous reformuler ?";
  } else {
    if (/(hi|hello|hey)/.test(q)) return "👋 Hello! How can I help?";
    if (/how are you/.test(q)) return "I'm just a bot, but I'm good! And you?";
    if (/help/.test(q)) return "Sure! What do you need help with?";
    if (/thank/.test(q)) return "You're welcome! 😊";
    if (/bye/.test(q)) return "Goodbye!";
    return "😕 Sorry, I didn't get that. Try again.";
  }
}

// ====== WEBSOCKET SETUP ======
let chatSocket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000; // 3 seconds

function setupWebSocket() {
  const roomName = "patient_default";
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${wsProtocol}://${window.location.host}/ws/chat/${roomName}/`;

  chatSocket = new WebSocket(wsUrl);

  chatSocket.onopen = () => {
    console.log('WebSocket connected');
    reconnectAttempts = 0;
    statusIndicator.textContent = translations.wsConnected[currentLanguage];
    statusIndicator.style.color = 'green';
  };

  chatSocket.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.sender === 'bot') {
        addBubble(data.message, 'bot');
        botReplyCount++;
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  chatSocket.onclose = (e) => {
    console.log('WebSocket disconnected:', e);
    statusIndicator.textContent = '';
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      console.log(`Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
      setTimeout(setupWebSocket, RECONNECT_DELAY);
    }
  };

  chatSocket.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
}

// Initialize WebSocket connection
setupWebSocket();

// ====== BOT REPLY FUNCTION ======
async function botReply(userText = '') {
  if (!userText) {
    addBubble(translations.newChat[currentLanguage], 'bot');
    return;
  }

  // Add thinking bubble
  const thinking = document.createElement('div');
  thinking.className = 'chat-line bot';
  thinking.innerHTML = `<div class="chat-emoji">🤖</div><div class="chat-bubble" id="thinking-bubble">${translations.thinking[currentLanguage]}<span id="dots">.</span></div>`;
  messagesEl.appendChild(thinking);
  scrollIfNeeded();

  const dotsEl = document.getElementById('dots');
  let dotCount = 1;
  const interval = setInterval(() => {
    dotCount = (dotCount + 1) % 4;
    dotsEl.textContent = '.'.repeat(dotCount || 1);
  }, 400);

  try {
    // Try WebSocket first if available
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
      chatSocket.send(JSON.stringify({
        type: 'text',
        content: userText,
        sender: 'user',
        language: currentLanguage
      }));
    } else {
      // Fallback to HTTP if WebSocket fails
      const response = await fetch('/chatbot/api/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
          'X-Language': currentLanguage
        },
        body: JSON.stringify({ message: userText })
      });

      const data = await response.json();
      clearInterval(interval);
      const bubbleDiv = thinking.querySelector('.chat-bubble');
      bubbleDiv.textContent = data.message || '🤔 No response received.';
      botReplyCount++;
    }
    persistCurrent();
  } catch (error) {
    clearInterval(interval);
    thinking.querySelector('.chat-bubble').textContent = botFallback(userText);
    console.error("Chatbot error:", error);
  }
}

// ====== EVENT LISTENERS ======
launcher.addEventListener('click', () => {
  const isHidden = getComputedStyle(panel).display === 'none';
  panel.style.display = isHidden ? 'flex' : 'none';

  if (isHidden) {
    input.focus();
    if (firstOpen) {
      current.messages.length === 0 ? showGreeting() : showWelcomeBack();
      firstOpen = false;
    }
  }
});

languageToggle.addEventListener('click', () => {
  currentLanguage = currentLanguage === 'en' ? 'fr' : 'en';
  updateUILanguage();
});

form.addEventListener('submit', e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addBubble(text, 'user');
  input.value = '';
  botReply(text);
});

let micBtn = document.getElementById('mic-button');
if (!micBtn) {
  micBtn = document.createElement('button');
  micBtn.type = 'button';
  micBtn.id = 'mic-button';
  micBtn.textContent = '🎙️';
  micBtn.title = 'Click to speak';
  Object.assign(micBtn.style, {
    marginLeft: '8px',
    background: '#007bff',
    border: 'none',
    color: 'white',
    fontSize: '1.2rem',
    padding: '6px 10px',
    borderRadius: '4px',
    cursor: 'pointer'
  });
  micBtn.addEventListener('mouseover', () => micBtn.style.background = '#0056b3');
  micBtn.addEventListener('mouseout', () => micBtn.style.background = '#007bff');
  micBtn.addEventListener('mousedown', () => micBtn.style.background = '#003f7f');
  micBtn.addEventListener('mouseup', () => micBtn.style.background = '#0056b3');
  form.appendChild(micBtn);
}

micBtn.addEventListener('click', () => {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    alert(currentLanguage === 'fr'
      ? "Reconnaissance vocale non supportée par votre navigateur."
      : "Speech recognition not supported in your browser.");
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.lang = currentLanguage === 'fr' ? 'fr-FR' : 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.start();
  micBtn.textContent = '🎤';

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    input.value = transcript;
    form.dispatchEvent(new Event('submit'));
  };

  recognition.onerror = (e) => alert(
    currentLanguage === 'fr'
      ? `Erreur vocale : ${e.error}`
      : `Voice error: ${e.error}`
  );
  recognition.onend = () => micBtn.textContent = '🎙️';
});

histBtn.onclick = () => {
  histDrawer.hidden = !histDrawer.hidden;
  if (!histDrawer.hidden) refreshHistory();
};

newBtn.onclick = () => {
  console.log('New chat clicked');
  fetch('/chatbot/api/chat/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
      'X-Language': currentLanguage
    },
    body: JSON.stringify({ message: 'restart' })
  }).then(() => {
    persistCurrent();
    startNewChat();
    histDrawer.hidden = true;
  });
};

window.addEventListener('beforeunload', persistCurrent);

// Initialize UI language
updateUILanguage();