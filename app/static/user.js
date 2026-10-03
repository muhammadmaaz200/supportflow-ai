const $ = (id) => document.getElementById(id);

let latestConversationId = null;

function esc(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[c])
  );
}

function addMessage(text, who) {
  const messages = $('messages');

  if (!messages) {
    console.error('messages element not found');
    return;
  }

  const wrap = document.createElement('div');
  wrap.className = `message ${who}`;

  if (who === 'user') {
    wrap.innerHTML = `
      <div>
        <small>You</small>
        <p>${esc(text)}</p>
      </div>
    `;
  } else {
    wrap.innerHTML = `
      <div class="avatar">SF</div>
      <div>
        <small>SupportFlow AI</small>
        <p>${esc(text)}</p>
      </div>
    `;
  }

  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

function setSignals(data) {
  const analysis = data?.analysis || {};

  const sentiment = $('sentimentValue');
  const emotion = $('emotionValue');
  const urgency = $('urgencyValue');
  const sourceList = $('sourceList');

  if (sentiment) {
    sentiment.textContent = analysis.sentiment || '—';
  }

  if (emotion) {
    emotion.textContent = analysis.emotion || '—';
  }

  if (urgency) {
    urgency.textContent = analysis.urgency || '—';
  }

  const sources = Array.isArray(data?.sources) ? data.sources : [];

  if (sourceList) {
    if (sources.length) {
      sourceList.innerHTML = sources.map(source => {
        const filename = esc(source?.filename || 'Unknown source');
        const score = Number(source?.score);

        return `
          <div>
            ${filename}
            ·
            ${Number.isFinite(score) ? (score * 100).toFixed(0) : '—'}%
          </div>
        `;
      }).join('');
    } else {
      sourceList.textContent =
        'No verified knowledge source matched this question.';
    }
  }

  latestConversationId = data?.id || null;
}

async function sendMessage(prefill = '') {
  const input = $('message');

  if (!input) {
    console.error('message input not found');
    return;
  }

  const value = (prefill || input.value || '').trim();

  if (!value) {
    return;
  }

  addMessage(value, 'user');

  input.value = '';

  const messages = $('messages');

  const pending = document.createElement('div');
  pending.className = 'message ai';

  pending.innerHTML = `
    <div class="avatar">SF</div>
    <div>
      <small>SupportFlow AI</small>
      <p>Thinking…</p>
    </div>
  `;

  if (messages) {
    messages.appendChild(pending);
    messages.scrollTop = messages.scrollHeight;
  }

  try {
    console.log('CHAT: sending request');

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      credentials: 'same-origin',
      body: JSON.stringify({
        message: value
      })
    });

    console.log('CHAT: response status =', res.status);
    console.log('CHAT: content-type =', res.headers.get('content-type'));

    const raw = await res.text();

    console.log('CHAT: raw response =', raw);

    let data = null;

    try {
      data = JSON.parse(raw);
    } catch (parseError) {
      console.error('CHAT: JSON parse failed =', parseError);

      throw new Error(
        `Server returned non-JSON response. HTTP ${res.status}. Response: ${raw.slice(0, 300)}`
      );
    }

    console.log('CHAT: parsed response =', data);

    if (!res.ok) {
      throw new Error(
        data?.message ||
        data?.detail ||
        data?.error ||
        `Request failed with HTTP ${res.status}`
      );
    }

    if (!data || typeof data !== 'object') {
      throw new Error('Invalid response received from server.');
    }

    if (!data.answer) {
      console.error('CHAT: answer missing:', data);

      throw new Error(
        data?.message ||
        data?.detail ||
        'Server response does not contain an answer.'
      );
    }

    if (pending && pending.parentNode) {
      pending.remove();
    }

    addMessage(data.answer, 'ai');

    setSignals(data);

    console.log('CHAT: success');

    loadConversations();

  } catch (error) {
    console.error('CHAT ERROR:', error);

    if (pending && pending.parentNode) {
      pending.remove();
    }

    addMessage(
      `Support service error: ${error?.message || 'Unknown error'}`,
      'ai'
    );
  }
}

async function loadConversations() {
  const rowsElement = $('myRows');

  if (!rowsElement) {
    return;
  }

  try {
    const res = await fetch('/api/my/conversations', {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      },
      credentials: 'same-origin'
    });

    const raw = await res.text();

    console.log('CONVERSATIONS response:', raw);

    let data;

    try {
      data = JSON.parse(raw);
    } catch (_) {
      throw new Error('Invalid conversations response.');
    }

    if (!res.ok) {
      throw new Error(
        data?.message ||
        data?.detail ||
        data?.error ||
        'Failed to load conversations.'
      );
    }

    const rows = Array.isArray(data?.conversations)
      ? data.conversations
      : [];

    if (!rows.length) {
      rowsElement.innerHTML = `
        <tr>
          <td colspan="5" class="empty">
            No conversations yet.
          </td>
        </tr>
      `;
      return;
    }

    rowsElement.innerHTML = rows.map(r => `
      <tr>
        <td>${esc(r?.created_at || '')}</td>

        <td>
          ${esc(r?.message || '')}
        </td>

        <td>
          <span class="tag tag-${esc(r?.sentiment || '')}">
            ${esc(r?.sentiment || '—')}
          </span>
        </td>

        <td>
          <span class="tag tag-${esc(r?.urgency || '')}">
            ${esc(r?.urgency || '—')}
          </span>
        </td>

        <td>
          <button
            class="btn btn-secondary"
            onclick="setLatest(${Number(r?.id) || 0})"
          >
            Open
          </button>
        </td>
      </tr>
    `).join('');

  } catch (error) {
    console.error('CONVERSATIONS ERROR:', error);

    rowsElement.innerHTML = `
      <tr>
        <td colspan="5" class="empty">
          Could not load conversations.
        </td>
      </tr>
    `;
  }
}

function setLatest(id) {
  latestConversationId = id;
  switchView('human');
}

async function requestHuman() {
  const status = $('humanStatus');

  if (!latestConversationId) {
    switchView('human');

    if (status) {
      status.textContent =
        'Start a chat first or choose a conversation from My Conversations.';
    }

    return;
  }

  const reasonInput = $('humanReason');

  const reason =
    reasonInput?.value.trim() ||
    'Customer requested human support';

  if (status) {
    status.textContent = 'Sending support request…';
  }

  try {
    const res = await fetch(
      `/api/my/conversations/${latestConversationId}/escalate`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          reason
        })
      }
    );

    const raw = await res.text();

    console.log('ESCALATION response:', raw);

    let data;

    try {
      data = JSON.parse(raw);
    } catch (_) {
      throw new Error('Invalid escalation response.');
    }

    if (!res.ok) {
      throw new Error(
        data?.message ||
        data?.detail ||
        data?.error ||
        `Request failed with HTTP ${res.status}`
      );
    }

    if (status) {
      status.textContent =
        `Support request #${data.escalation_id} is now open.`;
    }

  } catch (error) {
    console.error('ESCALATION ERROR:', error);

    if (status) {
      status.textContent =
        `Support request error: ${error?.message || 'Unknown error'}`;
    }
  }
}

function switchView(name) {
  document.querySelectorAll('.side-link').forEach(button => {
    button.classList.toggle(
      'active',
      button.dataset.view === name
    );
  });

  document.querySelectorAll('.view').forEach(view => {
    view.classList.toggle(
      'active',
      view.id === `view-${name}`
    );
  });

  if (name === 'conversations') {
    loadConversations();
  }
}

function initializeUserPage() {

  document.querySelectorAll('.side-link').forEach(button => {
    button.addEventListener('click', () => {
      switchView(button.dataset.view);
    });
  });

  document.querySelectorAll('[data-ask]').forEach(button => {
    button.addEventListener('click', () => {
      switchView('support');
      sendMessage(button.dataset.ask);
    });
  });

  const chatForm = $('chatForm');

  if (chatForm) {
    chatForm.addEventListener('submit', event => {
      event.preventDefault();
      sendMessage();
    });
  }

  const escalateLatest = $('escalateLatest');

  if (escalateLatest) {
    escalateLatest.addEventListener('click', () => {
      switchView('human');
      requestHuman();
    });
  }

  const humanSubmit = $('humanSubmit');

  if (humanSubmit) {
    humanSubmit.addEventListener('click', requestHuman);
  }

  loadConversations();

  console.log('SupportFlow user.js loaded successfully');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeUserPage);
} else {
  initializeUserPage();
}