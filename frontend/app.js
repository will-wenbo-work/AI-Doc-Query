const BACKEND = window.BACKEND_URL || 'http://localhost:8000';

const pdfInput = document.getElementById('pdfInput');
const fileDrop = document.getElementById('fileDrop');
const fileInfo = document.getElementById('fileInfo');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const sendBtn = document.getElementById('sendBtn');
const questionInput = document.getElementById('questionInput');
const messages = document.getElementById('messages');

let selectedFile = null;
let currentDocId = null;

function appendMessage(role, text){
  const el = document.createElement('div');
  el.className = 'message ' + (role === 'user' ? 'user' : 'assistant');
  el.textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

// File selection handlers
pdfInput.addEventListener('change', (e)=>{
  const f = e.target.files[0];
  onFileSelected(f);
});

fileDrop.addEventListener('dragover', (e)=>{e.preventDefault(); fileDrop.classList.add('drag');});
fileDrop.addEventListener('dragleave', (e)=>{fileDrop.classList.remove('drag');});
fileDrop.addEventListener('drop', (e)=>{
  e.preventDefault(); fileDrop.classList.remove('drag');
  const f = e.dataTransfer.files[0];
  onFileSelected(f);
});

function onFileSelected(f){
  if(!f) return;
  if(f.type !== 'application/pdf'){
    fileInfo.textContent = 'Please select a PDF file.';
    selectedFile = null;
    uploadBtn.disabled = true;
    return;
  }
  selectedFile = f;
  fileInfo.textContent = `${f.name} — ${(f.size/1024/1024).toFixed(2)} MB`;
  uploadBtn.disabled = false;
}

uploadBtn.addEventListener('click', async ()=>{
  if(!selectedFile) return;
  uploadBtn.disabled = true;
  uploadStatus.textContent = 'Uploading...';
  const fd = new FormData();
  fd.append('file', selectedFile);
  try{
    const res = await fetch(`${BACKEND}/upload_pdf`, {method:'POST', body:fd});
    if(!res.ok){
      const txt = await res.text();
      throw new Error(txt || res.statusText);
    }
    const data = await res.json();
    // backend should return {doc_id: '...'} or similar
    currentDocId = data.doc_id || data.id || data.filename || selectedFile.name;
    uploadStatus.textContent = 'Upload complete.';
    sendBtn.disabled = false;
    appendMessage('assistant', 'Document uploaded. You can now ask questions.');
  }catch(err){
    console.error(err);
    uploadStatus.textContent = 'Upload failed: ' + (err.message || err);
    uploadBtn.disabled = false;
  }
});

// Chat send
sendBtn.addEventListener('click', sendQuestion);
questionInput.addEventListener('keydown', (e)=>{
  if(e.key === 'Enter') sendQuestion();
});

async function sendQuestion(){
  const q = questionInput.value.trim();
  if(!q) return;
  appendMessage('user', q);
  questionInput.value = '';
  sendBtn.disabled = true;

  const payload = {question: q, doc_id: currentDocId};
  try{
    const res = await fetch(`${BACKEND}/chat`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    if(!res.ok){
      const txt = await res.text();
      throw new Error(txt || res.statusText);
    }

    const data = await res.json();
    // expected backend response: {answer: '...'} or {answer_text: '...'}
    const answer = data.answer || data.answer_text || data.text || JSON.stringify(data);
    appendMessage('assistant', answer);
  }catch(err){
    console.error(err);
    appendMessage('assistant', 'Error getting answer: ' + (err.message || err));
  }finally{
    sendBtn.disabled = false;
  }
}

// Small UX: if page loads and backend is not available, we still allow local file select
// You can set BACKEND_URL on the page to point to a different host/port.
