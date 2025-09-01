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
    en: "Hello! I'm MediAI, your medical assistant. I can help with general health questions, symptom information, and first aid advice. How can I help you today?",
    fr: "Bonjour ! Je suis MediAI, votre assistant médical. Je peux vous aider avec des questions générales sur la santé, des informations sur les symptômes et des conseils de premiers soins. Comment puis-je vous aider aujourd'hui ?"
  },
  welcomeBack: {
    en: "👋 Welcome back! I'm here to help with your medical questions.",
    fr: "👋 Bon retour ! Je suis là pour vous aider avec vos questions médicales."
  },
  newChat: {
    en: "👋 New chat started with MediAI - Your Medical Assistant",
    fr: "👋 Nouvelle conversation avec MediAI - Votre Assistant Médical"
  },
  thinking: {
    en: "MediAI is thinking",
    fr: "MediAI réfléchit"
  },
  inputPlaceholder: {
    en: "Type your medical question or concern...",
    fr: "Tapez votre question ou préoccupation médicale..."
  },
  error: {
    en: "I'm having trouble connecting to my medical knowledge base. Please try again or rephrase your question.",
    fr: "J'ai des difficultés à me connecter à ma base de connaissances médicales. Veuillez réessayer ou reformuler votre question."
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

// ====== UTILITY FUNCTIONS ======
const loadConvos = () => JSON.parse(localStorage.getItem(LS_KEY) || '[]');
const saveConvos = (c) => localStorage.setItem(LS_KEY, JSON.stringify(c));

function scrollIfNeeded() {
  if (botReplyCount > 0) {
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
  addBubble(translations.newChat[currentLanguage], 'bot');
  showGreeting();
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

// ====== MEDICAL AI INTEGRATION ======
async function getMedicalAIResponse(userText) {
  try {
    const response = await fetch('/chatbot/api/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        'X-Language': currentLanguage
      },
      body: JSON.stringify({
        message: userText,
        language: currentLanguage
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    if (data.message) {
      return data.message;
    } else if (data.error) {
      throw new Error(data.error);
    } else {
      throw new Error('No response from medical AI service');
    }
  } catch (error) {
    console.error('Medical AI error:', error);
    
    // Try CSV fallback as last resort
    try {
      const csvResponse = await fetch('/chatbot/api/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
          'X-Language': currentLanguage
        },
        body: JSON.stringify({
          message: userText,
          language: currentLanguage,
          use_csv_fallback: true
        })
      });
      
      if (csvResponse.ok) {
        const csvData = await csvResponse.json();
        return csvData.message || translations.error[currentLanguage];
      }
    } catch (csvError) {
      console.error('CSV fallback also failed:', csvError);
    }
    
    return translations.error[currentLanguage];
  }
}

// ====== BOT REPLY FUNCTION ======
async function botReply(userText = '') {
  if (!userText) {
    addBubble(translations.newChat[currentLanguage], 'bot');
    showGreeting();
    return;
  }

  // Add thinking bubble
  const thinking = document.createElement('div');
  thinking.className = 'chat-line bot';
  thinking.id = 'thinking-wrap';
  thinking.innerHTML = `<div class="chat-emoji">🤖</div><div class="chat-bubble" id="thinking-bubble">${translations.thinking[currentLanguage]}<span id="dots">.</span></div>`;
  messagesEl.appendChild(thinking);
  scrollIfNeeded();

  const dotsEl = document.getElementById('dots');
  let dotCount = 1;
  const interval = setInterval(() => {
    dotCount = (dotCount + 1) % 4;
    if (dotsEl) dotsEl.textContent = '.'.repeat(dotCount || 1);
  }, 400);

  try {
    // Get response from Medical AI
    const response = await getMedicalAIResponse(userText);
    
    clearInterval(interval);
    // Remove thinking bubble
    const wrap = document.getElementById('thinking-wrap');
    if (wrap) wrap.remove();

    // Add actual response
    addBubble(response, 'bot');
    botReplyCount++;
    
    persistCurrent();
  } catch (error) {
    clearInterval(interval);
    const wrap = document.getElementById('thinking-wrap');
    if (wrap) wrap.remove();
    
    // Final fallback response
    addBubble(translations.error[currentLanguage], 'bot');
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
      if (current.messages.length === 0) {
        showGreeting();
      } else {
        showWelcomeBack();
      }
      firstOpen = false;
    }
  }
});

languageToggle.addEventListener('click', () => {
  currentLanguage = currentLanguage === 'en' ? 'fr' : 'en';
  updateUILanguage();
  
  // Notify user of language change
  const changeMsg = currentLanguage === 'en' 
    ? "Language changed to English. How can I help with your medical questions?" 
    : "Langue changée en Français. Comment puis-je vous aider avec vos questions médicales?";
  addBubble(changeMsg, 'bot');
});

newBtn.addEventListener('click', () => {
  startNewChat();
});

histBtn.addEventListener('click', () => {
  const isHidden = histDrawer.hidden;
  if (isHidden) {
    refreshHistory();
  }
  histDrawer.hidden = !isHidden;
});

form.addEventListener('submit', e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addBubble(text, 'user');
  input.value = '';
  botReply(text);
});

// Initialize UI language
updateUILanguage();

// Auto-focus input when panel opens
const observer = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    if (mutation.attributeName === 'style') {
      if (getComputedStyle(panel).display !== 'none') {
        input.focus();
      }
    }
  });
});

observer.observe(panel, { attributes: true });