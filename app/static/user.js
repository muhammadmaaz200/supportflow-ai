const $ = (id) => document.getElementById(id);
let latestConversationId = null;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
function addMessage(text, who) {
  const wrap = document.createElement('div');
  wrap.className = `message ${who}`;
  wrap.innerHTML = who === 'user'
    ? `<div><small>You</small><p>${esc(text)}</p></div>`
    : `<div class="avatar">SF</div><div><small>SupportFlow AI</small><p>${esc(text)}</p></div>`;
  $('messages').appendChild(wrap);
  $('messages').scrollTop = $('messages').scrollHeight;
}
function setSignals(data) {
  const a = data.analysis || {};
  $('sentimentValue').textContent = a.sentiment || '—';
  $('emotionValue').textContent = a.emotion || '—';
  $('urgencyValue').textContent = a.urgency || '—';
  const sources = data.sources || [];
  $('sourceList').innerHTML = sources.length
    ? sources.map(s => `<div>${esc(s.filename)} · ${(Number(s.score) * 100).toFixed(0)}%</div>`).join('')
    : 'No verified knowledge source matched this question.';
  latestConversationId = data.id || null;
}
async function sendMessage(prefill='') {
  const input = $('message');
  const value = (prefill || input.value).trim();
  if (!value) return;
  addMessage(value, 'user');
  input.value = '';
  const pending = document.createElement('div');
  pending.className = 'message ai';
  pending.innerHTML = `<div class="avatar">SF</div><div><small>SupportFlow AI</small><p>Thinking…</p></div>`;
  $('messages').appendChild(pending);
  $('messages').scrollTop = $('messages').scrollHeight;
  try {
    const res = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:value})});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    pending.remove();
    addMessage(data.answer || 'I could not generate a response.', 'ai');
    setSignals(data);
  } catch (error) {
    pending.remove();
    addMessage('The support service could not be reached right now. Please try again.', 'ai');
  }
}
async function loadConversations() {
  try {
    const res = await fetch('/api/my/conversations');
    if (!res.ok) throw new Error('failed');
    const data = await res.json();
    const rows = data.conversations || [];
    $('myRows').innerHTML = rows.length ? rows.map(r => `
      <tr><td>${esc(r.created_at)}</td><td>${esc(r.message)}</td><td><span class="tag tag-${esc(r.sentiment)}">${esc(r.sentiment)}</span></td><td><span class="tag tag-${esc(r.urgency)}">${esc(r.urgency)}</span></td><td><button class="btn btn-secondary" onclick="setLatest(${r.id})">Open</button></td></tr>
    `).join('') : '<tr><td colspan="5" class="empty">No conversations yet.</td></tr>';
  } catch (_) {}
}
function setLatest(id){ latestConversationId = id; switchView('human'); }
async function requestHuman() {
  if (!latestConversationId) { switchView('human'); $('humanStatus').textContent = 'Start a chat first or choose a conversation from My Conversations.'; return; }
  const reason = $('humanReason').value.trim() || 'Customer requested human support';
  $('humanStatus').textContent = 'Sending support request…';
  const res = await fetch(`/api/my/conversations/${latestConversationId}/escalate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason})});
  const data = await res.json();
  $('humanStatus').textContent = res.ok ? `Support request #${data.escalation_id} is now open.` : (data.detail || 'Request failed.');
}
function switchView(name){
  document.querySelectorAll('.side-link').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${name}`));
  if(name==='conversations') loadConversations();
}
document.querySelectorAll('.side-link').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
document.querySelectorAll('[data-ask]').forEach(b=>b.addEventListener('click',()=>{switchView('support');sendMessage(b.dataset.ask)}));
$('chatForm').addEventListener('submit',e=>{e.preventDefault();sendMessage()});
$('escalateLatest').addEventListener('click',()=>{switchView('human');requestHuman()});
$('humanSubmit').addEventListener('click',requestHuman);
loadConversations();
