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

  const wrap = document.createElement('div');

  wrap.className = `message ${who}`;

  wrap.innerHTML = who === 'user'
    ? `
      <div>
        <small>You</small>
        <p>${esc(text)}</p>
      </div>
    `
    : `
      <div class="avatar">SF</div>
      <div>
        <small>SupportFlow AI</small>
        <p>${esc(text)}</p>
      </div>
    `;

  $('messages').appendChild(wrap);

  $('messages').scrollTop =
    $('messages').scrollHeight;
}


function setSignals(data) {

  const a = data.analysis || {};

  $('sentimentValue').textContent =
    a.sentiment || '—';

  $('emotionValue').textContent =
    a.emotion || '—';

  $('urgencyValue').textContent =
    a.urgency || '—';


  const sources =
    data.sources || [];


  $('sourceList').innerHTML =
    sources.length
      ? sources.map(s =>
          `<div>
            ${esc(s.filename)}
            · ${(Number(s.score) * 100).toFixed(0)}%
          </div>`
        ).join('')
      : 'No verified knowledge source matched this question.';


  latestConversationId =
    data.id || null;
}


/* ============================================================
   SEND CHAT MESSAGE
   ============================================================ */

async function sendMessage(prefill = '') {

  const input = $('message');

  const value =
    (prefill || input.value).trim();


  if (!value) {
    return;
  }


  addMessage(
    value,
    'user'
  );


  input.value = '';


  const pending =
    document.createElement('div');


  pending.className =
    'message ai';


  pending.innerHTML = `
    <div class="avatar">SF</div>
    <div>
      <small>SupportFlow AI</small>
      <p>Thinking…</p>
    </div>
  `;


  $('messages').appendChild(
    pending
  );


  $('messages').scrollTop =
    $('messages').scrollHeight;


  try {

    console.log(
      'CHAT: sending request'
    );


    const res = await fetch(
      '/api/chat',
      {
        method: 'POST',

        headers: {
          'Content-Type':
            'application/json'
        },

        body: JSON.stringify({
          message: value
        })
      }
    );


    console.log(
      'CHAT: response status =',
      res.status
    );


    /* --------------------------------------------------------
       Read response safely
    -------------------------------------------------------- */

    const rawText =
      await res.text();


    console.log(
      'CHAT: raw response =',
      rawText
    );


    let data = {};


    try {

      data =
        rawText
          ? JSON.parse(rawText)
          : {};

    } catch (jsonError) {

      console.error(
        'CHAT JSON ERROR:',
        jsonError
      );

      throw new Error(
        `Server returned invalid JSON. HTTP ${res.status}`
      );
    }


    console.log(
      'CHAT: parsed response =',
      data
    );


    /* --------------------------------------------------------
       Backend error
    -------------------------------------------------------- */

    if (!res.ok) {

      const backendMessage =
        data.message ||
        data.detail ||
        data.error ||
        `HTTP ${res.status}`;

      console.error(
        'CHAT BACKEND ERROR:',
        backendMessage
      );

      throw new Error(
        backendMessage
      );
    }


    /* --------------------------------------------------------
       Validate successful response
    -------------------------------------------------------- */

    if (
      !data ||
      typeof data !== 'object'
    ) {

      throw new Error(
        'Invalid response from chat service.'
      );
    }


    console.log(
      'CHAT: answer =',
      data.answer
    );


    pending.remove();


    addMessage(
      data.answer ||
      'I could not generate a response.',
      'ai'
    );


    setSignals(data);


    /*
     * Refresh conversation history
     */
    loadConversations();


  } catch (error) {

    console.error(
      'CHAT ERROR:',
      error
    );


    pending.remove();


    /*
     * IMPORTANT:
     * Show the actual backend error temporarily
     * so we can identify the problem.
     */

    addMessage(
      `Support service error: ${
        error.message ||
        'Unknown error'
      }`,
      'ai'
    );
  }
}


/* ============================================================
   LOAD CONVERSATIONS
   ============================================================ */

async function loadConversations() {

  try {

    const res =
      await fetch(
        '/api/my/conversations'
      );


    if (!res.ok) {

      throw new Error(
        `HTTP ${res.status}`
      );
    }


    const data =
      await res.json();


    const rows =
      data.conversations || [];


    $('myRows').innerHTML =
      rows.length
        ? rows.map(r => `
          <tr>
            <td>${esc(r.created_at)}</td>

            <td>
              ${esc(r.message)}
            </td>

            <td>
              <span class="tag tag-${esc(r.sentiment)}">
                ${esc(r.sentiment)}
              </span>
            </td>

            <td>
              <span class="tag tag-${esc(r.urgency)}">
                ${esc(r.urgency)}
              </span>
            </td>

            <td>
              <button
                class="btn btn-secondary"
                onclick="setLatest(${r.id})"
              >
                Open
              </button>
            </td>
          </tr>
        `).join('')
        : `
          <tr>
            <td
              colspan="5"
              class="empty"
            >
              No conversations yet.
            </td>
          </tr>
        `;


  } catch (error) {

    console.error(
      'LOAD CONVERSATIONS ERROR:',
      error
    );

  }
}


/* ============================================================
   SET LATEST CONVERSATION
   ============================================================ */

function setLatest(id) {

  latestConversationId =
    id;

  switchView(
    'human'
  );
}


/* ============================================================
   REQUEST HUMAN SUPPORT
   ============================================================ */

async function requestHuman() {

  if (!latestConversationId) {

    switchView(
      'human'
    );

    $('humanStatus').textContent =
      'Start a chat first or choose a conversation from My Conversations.';

    return;
  }


  const reason =
    $('humanReason').value.trim()
    ||
    'Customer requested human support';


  $('humanStatus').textContent =
    'Sending support request…';


  try {

    const res =
      await fetch(
        `/api/my/conversations/${latestConversationId}/escalate`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json'
          },

          body: JSON.stringify({
            reason
          })
        }
      );


    const data =
      await res.json();


    $('humanStatus').textContent =
      res.ok
        ? `Support request #${data.escalation_id} is now open.`
        : (
            data.detail ||
            data.message ||
            'Request failed.'
          );


  } catch (error) {

    console.error(
      'HUMAN SUPPORT ERROR:',
      error
    );


    $('humanStatus').textContent =
      `Error: ${
        error.message ||
        'Request failed.'
      }`;
  }
}


/* ============================================================
   SWITCH VIEW
   ============================================================ */

function switchView(name) {

  document
    .querySelectorAll('.side-link')
    .forEach(
      b =>
        b.classList.toggle(
          'active',
          b.dataset.view === name
        )
    );


  document
    .querySelectorAll('.view')
    .forEach(
      v =>
        v.classList.toggle(
          'active',
          v.id === `view-${name}`
        )
    );


  if (
    name === 'conversations'
  ) {

    loadConversations();

  }
}


/* ============================================================
   SIDEBAR
   ============================================================ */

document
  .querySelectorAll('.side-link')
  .forEach(
    b =>
      b.addEventListener(
        'click',
        () =>
          switchView(
            b.dataset.view
          )
      )
  );


/* ============================================================
   QUICK QUESTIONS
   ============================================================ */

document
  .querySelectorAll('[data-ask]')
  .forEach(
    b =>
      b.addEventListener(
        'click',
        () => {

          switchView(
            'support'
          );

          sendMessage(
            b.dataset.ask
          );

        }
      )
  );


/* ============================================================
   CHAT FORM
   ============================================================ */

$('chatForm')
  .addEventListener(
    'submit',
    e => {

      e.preventDefault();

      sendMessage();

    }
  );


/* ============================================================
   ESCALATE LATEST
   ============================================================ */

$('escalateLatest')
  .addEventListener(
    'click',
    () => {

      switchView(
        'human'
      );

      requestHuman();

    }
  );


/* ============================================================
   HUMAN SUPPORT
   ============================================================ */

$('humanSubmit')
  .addEventListener(
    'click',
    requestHuman
  );


/* ============================================================
   INITIAL LOAD
   ============================================================ */

loadConversations();