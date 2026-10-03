const $ = (id) => document.getElementById(id);
function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
function tag(value){return `<span class="tag tag-${esc(value)}">${esc(value || '—')}</span>`}
function switchView(name){
  document.querySelectorAll('.side-link').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${name}`));
  const loaders={knowledge:loadKnowledge,conversations:loadConversations,escalations:loadEscalations,audit:loadAudit,overview:refresh};
  if(loaders[name]) loaders[name]();
}
document.querySelectorAll('.side-link').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
async function refresh(){
  try{
    const d=await (await fetch('/api/dashboard')).json();
    $('kpiDocuments').textContent=d.documents??0;$('kpiChunks').textContent=d.chunks??0;$('kpiConversations').textContent=d.conversations??0;$('kpiUrgent').textContent=d.urgent??0;$('kpiOpenEsc').textContent=d.open_escalations??0;
    const s=d.sentiment||{}; const total=(s.positive||0)+(s.neutral||0)+(s.negative||0)||1;
    [['pos',s.positive||0],['neu',s.neutral||0],['neg',s.negative||0]].forEach(([k,n])=>{$(`${k}Count`).textContent=n;$(`${k}Bar`).style.width=`${n/total*100}%`});
    $('analyticsNegative').textContent=s.negative||0;$('analyticsUrgent').textContent=d.urgent||0;$('analyticsEscalated').textContent=d.escalated||0;
    const cs=await (await fetch('/api/conversations')).json(); const rows=cs.conversations||[];
    $('recentRows').innerHTML=rows.slice(0,8).map(r=>`<tr><td>${esc(r.created_at)}</td><td>${esc(r.user_email)}</td><td>${esc(r.message)}</td><td>${tag(r.sentiment)}</td><td>${tag(r.urgency)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">No conversations yet.</td></tr>';
  }catch(e){}
}
async function loadKnowledge(){try{const d=await (await fetch('/api/knowledge')).json();const rows=d.documents||[];$('knowledgeRows').innerHTML=rows.length?rows.map(x=>`<tr><td>${esc(x.filename)}</td><td>${x.chunks}</td></tr>`).join(''):'<tr><td colspan="2" class="empty">No documents indexed.</td></tr>'}catch(e){}}
async function loadConversations(){try{const d=await (await fetch('/api/conversations')).json();const rows=d.conversations||[];$('conversationRows').innerHTML=rows.length?rows.map(r=>`<tr><td>${esc(r.created_at)}</td><td>${esc(r.user_email)}</td><td>${esc(r.message)}</td><td>${tag(r.sentiment)}</td><td>${esc(r.emotion)}</td><td>${tag(r.urgency)}</td><td>${r.escalated?'Yes':'No'}</td></tr>`).join(''):'<tr><td colspan="7" class="empty">No conversations yet.</td></tr>'}catch(e){}}
async function loadEscalations(){try{const d=await (await fetch('/api/escalations')).json();const rows=d.escalations||[];$('escalationRows').innerHTML=rows.length?rows.map(r=>`<tr><td>${esc(r.created_at)}</td><td>${esc(r.user_email)}</td><td>${esc(r.reason)}</td><td>${tag(r.status)}</td><td>${r.status==='open'?`<button class="btn btn-secondary" onclick="setEscalation(${r.id},'in_progress')">Start</button>`:r.status==='in_progress'?`<button class="btn btn-secondary" onclick="setEscalation(${r.id},'resolved')">Resolve</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No escalations yet.</td></tr>'}catch(e){}}
async function loadAudit(){try{const d=await (await fetch('/api/audit')).json();const rows=d.audit||[];$('auditRows').innerHTML=rows.length?rows.map(r=>`<tr><td>${esc(r.created_at)}</td><td>${esc(r.actor_email)}</td><td>${esc(r.action)}</td><td>${esc(r.details)}</td><td>${tag(r.status)}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No audit records yet.</td></tr>'}catch(e){}}
async function setEscalation(id,status){const res=await fetch(`/api/escalations/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});if(res.ok)loadEscalations()}
$('uploadForm').addEventListener('submit',async e=>{e.preventDefault();const file=$('kbFile').files[0];if(!file)return;$('uploadStatus').textContent='Uploading and indexing…';const fd=new FormData();fd.append('file',file);try{const res=await fetch('/api/knowledge/upload',{method:'POST',body:fd});const d=await res.json();$('uploadStatus').textContent=res.ok?`${d.message} ${d.chunks} chunks.`:(d.detail||'Upload failed.');if(res.ok){$('uploadForm').reset();refresh();loadKnowledge()}}catch(e){$('uploadStatus').textContent='Upload failed.'}});
refresh();loadKnowledge();setInterval(refresh,15000);
