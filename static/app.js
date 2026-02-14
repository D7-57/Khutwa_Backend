const API = ""; // same origin (FastAPI serves static + API)

const els = {
  token: document.getElementById("token"),
  saveToken: document.getElementById("saveToken"),
  authStatus: document.getElementById("authStatus"),

  roleName: document.getElementById("roleName"),
  numQuestions: document.getElementById("numQuestions"),
  followupMax: document.getElementById("followupMax"),
  startBtn: document.getElementById("startBtn"),
  sessionId: document.getElementById("sessionId"),

  promptBox: document.getElementById("promptBox"),
  playPromptBtn: document.getElementById("playPromptBtn"),
  audioPlayer: document.getElementById("audioPlayer"),
  debug: document.getElementById("debug"),

  recBtn: document.getElementById("recBtn"),
  stopBtn: document.getElementById("stopBtn"),
  recStatus: document.getElementById("recStatus"),

  sendAudioBtn: document.getElementById("sendAudioBtn"),
  transcribeOnlyBtn: document.getElementById("transcribeOnlyBtn"),

  answerText: document.getElementById("answerText"),
  sendTextBtn: document.getElementById("sendTextBtn"),
};

let sessionId = null;
let lastPromptText = "";
let mediaRecorder = null;
let recordedChunks = [];
let recordedBlob = null;

function getToken() {
  const t = (localStorage.getItem("access_token") || "").trim();
  return t;
}
function setToken(t) {
  localStorage.setItem("access_token", (t || "").trim());
}
function authHeaders(json = true) {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}
function setEnabled(enabled) {
  els.startBtn.disabled = !enabled;
  els.playPromptBtn.disabled = !enabled || !lastPromptText;
  els.recBtn.disabled = !enabled;
  els.sendTextBtn.disabled = !enabled || !sessionId;
  els.sendAudioBtn.disabled = !enabled || !recordedBlob || !sessionId;
  els.transcribeOnlyBtn.disabled = !enabled || !recordedBlob;
}

function showDebug(obj) {
  els.debug.textContent = JSON.stringify(obj, null, 2);
}
function setPrompt(text) {
  lastPromptText = text || "";
  els.promptBox.textContent = lastPromptText || "No prompt yet.";
  els.playPromptBtn.disabled = !lastPromptText;
}

async function startInterview() {
  const role = els.roleName.value.trim();
  const num = Number(els.numQuestions.value || 3);
  const follow = Number(els.followupMax.value || 1);

  const url = `${API}/interviews/start?role_name=${encodeURIComponent(role)}&num_questions=${num}&followup_max=${follow}`;
  const r = await fetch(url, { method: "POST", headers: authHeaders(false) });
  if (!r.ok) throw new Error(await r.text());

  const data = await r.json();
  sessionId = data.session_id;
  els.sessionId.textContent = sessionId;

  setPrompt(data.prompt_text);
  showDebug(data);

  // now we can send turns
  els.sendTextBtn.disabled = false;
  els.recBtn.disabled = false;
}

async function playTTS(text) {
  const url = `${API}/audio/prompt-audio?text=${encodeURIComponent(text)}`;
  const r = await fetch(url, { headers: authHeaders(false) });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  const objectUrl = URL.createObjectURL(blob);
  els.audioPlayer.src = objectUrl;
  await els.audioPlayer.play();
}

async function sendTurnText(answerText) {
  if (!sessionId) throw new Error("No session");

  const fd = new FormData();
  fd.append("answer_text", answerText);

  const r = await fetch(`${API}/interviews/${sessionId}/turn`, {
    method: "POST",
    headers: authHeaders(false), // don't set Content-Type for FormData
    body: fd,
  });
  if (!r.ok) throw new Error(await r.text());
  const data = await r.json();
  setPrompt(data.prompt_text);
  showDebug(data);
  return data;
}

async function sendTurnAudio(blob) {
  if (!sessionId) throw new Error("No session");

  const fd = new FormData();
  fd.append("audio", blob, "answer.webm");

  const r = await fetch(`${API}/interviews/${sessionId}/turn`, {
    method: "POST",
    headers: authHeaders(false),
    body: fd,
  });
  if (!r.ok) throw new Error(await r.text());
  const data = await r.json();
  setPrompt(data.prompt_text);
  showDebug(data);
  return data;
}

async function transcribeOnly(blob) {
  const fd = new FormData();
  fd.append("audio", blob, "answer.webm");

  const r = await fetch(`${API}/audio/transcribe`, {
    method: "POST",
    headers: authHeaders(false),
    body: fd,
  });
  if (!r.ok) throw new Error(await r.text());
  const data = await r.json();
  showDebug({ transcribe_only: data });
  return data;
}

async function initMic() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  // use webm/opus (Chrome/Edge)
  const options = { mimeType: "audio/webm;codecs=opus" };
  mediaRecorder = new MediaRecorder(stream, options);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordedChunks.push(e.data);
  };

  mediaRecorder.onstop = () => {
    recordedBlob = new Blob(recordedChunks, { type: "audio/webm" });
    recordedChunks = [];
    els.recStatus.textContent = `Recorded ${(recordedBlob.size / 1024).toFixed(1)} KB`;

    // enable buttons that need blob
    els.sendAudioBtn.disabled = !sessionId;
    els.transcribeOnlyBtn.disabled = false;
  };
}

els.saveToken.addEventListener("click", () => {
  setToken(els.token.value);
  const ok = !!getToken();
  els.authStatus.textContent = ok ? "✅ token saved" : "❌ missing token";
  setEnabled(ok);
});

els.startBtn.addEventListener("click", async () => {
  try {
    await startInterview();
    setEnabled(true);
  } catch (e) {
    alert(`Start failed: ${e.message}`);
  }
});

els.playPromptBtn.addEventListener("click", async () => {
  try {
    await playTTS(lastPromptText);
  } catch (e) {
    alert(`TTS failed: ${e.message}`);
  }
});

els.sendTextBtn.addEventListener("click", async () => {
  try {
    const txt = els.answerText.value.trim();
    if (!txt) return alert("Type an answer first");
    await sendTurnText(txt);
    els.answerText.value = "";
  } catch (e) {
    alert(`Turn failed: ${e.message}`);
  }
});

els.recBtn.addEventListener("click", async () => {
  try {
    if (!mediaRecorder) await initMic();
    recordedBlob = null;
    els.sendAudioBtn.disabled = true;
    els.transcribeOnlyBtn.disabled = true;

    els.recStatus.textContent = "Recording...";
    els.recBtn.disabled = true;
    els.stopBtn.disabled = false;

    mediaRecorder.start();
  } catch (e) {
    alert(`Mic failed: ${e.message}`);
  }
});

els.stopBtn.addEventListener("click", async () => {
  try {
    if (!mediaRecorder) return;
    mediaRecorder.stop();

    els.stopBtn.disabled = true;
    els.recBtn.disabled = false;
  } catch (e) {
    alert(`Stop failed: ${e.message}`);
  }
});

els.sendAudioBtn.addEventListener("click", async () => {
  try {
    if (!recordedBlob) return alert("Record audio first");
    await sendTurnAudio(recordedBlob);
  } catch (e) {
    alert(`Audio turn failed: ${e.message}`);
  }
});

els.transcribeOnlyBtn.addEventListener("click", async () => {
  try {
    if (!recordedBlob) return alert("Record audio first");
    await transcribeOnly(recordedBlob);
  } catch (e) {
    alert(`Transcribe failed: ${e.message}`);
  }
});

// boot
(() => {
  const t = getToken();
  if (t) {
    els.token.value = t;
    els.authStatus.textContent = "✅ token loaded from storage";
    setEnabled(true);
  } else {
    els.authStatus.textContent = "Paste token to enable";
    setEnabled(false);
  }
})();
