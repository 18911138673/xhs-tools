// ===== 用户系统 =====
let USER_ID = localStorage.getItem("xhs_user_id") || "";
let DEVICE_ID = localStorage.getItem("xhs_device_id") || "";
const API_BASE = "";  // same origin

async function initUser() {
    if (!DEVICE_ID) {
        DEVICE_ID = "device_" + Math.random().toString(36).slice(2, 10);
        localStorage.setItem("xhs_device_id", DEVICE_ID);
    }
    try {
        const resp = await fetch(API_BASE + "/api/user/init", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({device_id: DEVICE_ID})
        });
        const data = await resp.json();
        if (data.success) {
            USER_ID = data.user.id;
            localStorage.setItem("xhs_user_id", USER_ID);
            updateUsage(data.user.remaining);
        }
    } catch(e) {
        console.log("User init failed:", e);
    }
}

function updateUsage(remaining) {
    const el = document.getElementById("remaining-count");
    if (el) {
        el.textContent = remaining;
        el.style.color = remaining <= 1 ? "#FF2442" : "#1d1d1f";
    }
}

function getHeaders() {
    return {"Content-Type": "application/json", "X-User-Id": USER_ID};
}

// ===== 批量提取 =====
async function batchExtract() {
    const text = document.getElementById("batch-urls").value.trim();
    if (!text) { showError("batch", "请输入链接"); return; }
    const urls = text.split("\n").map(u => u.trim()).filter(u => u);
    if (urls.length > 10) { showError("batch", "一次最多10个链接"); return; }
    if (urls.length === 0) { showError("batch", "没有有效链接"); return; }

    hideError("batch");
    document.getElementById("batch-btn").disabled = true;
    document.getElementById("batch-btn").textContent = "⏳ 处理中...";

    try {
        const resp = await fetch(API_BASE + "/api/batch_extract", {
            method: "POST", headers: getHeaders(),
            body: JSON.stringify({urls})
        });
        const data = await resp.json();
        if (!data.success) {
            if (data.limited) { showToast("⚠️ " + data.error); return; }
            showError("batch", data.error); return;
        }
        displayBatchResult(data.data);
        updateUsageFromServer();
    } catch(e) {
        showError("batch", "请求失败");
    } finally {
        document.getElementById("batch-btn").disabled = false;
        document.getElementById("batch-btn").textContent = "🚀 批量提取";
    }
}

function displayBatchResult(results) {
    const div = document.getElementById("batch-output");
    div.innerHTML = "";
    const container = document.getElementById("batch-result");
    container.classList.remove("hidden");

    results.forEach((r, i) => {
        const card = document.createElement("div");
        card.className = "batch-item";
        card.style.cssText = "padding:16px;margin-bottom:12px;background:#fff;border-radius:10px;border:1px solid #e8e8ed";
        if (r.success) {
            card.innerHTML = `
                <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                    <strong style="color:#1F3864">#${i+1} ${r.data.title || "无标题"}</strong>
                    <span style="font-size:12px;color:#86868b">${r.data.author || ""}</span>
                </div>
                <div style="font-size:13px;color:#444;line-height:1.6;margin-bottom:8px;white-space:pre-wrap;max-height:80px;overflow:hidden">${r.data.desc || "无文案"}</div>
                <button class="btn-copy" style="padding:6px 14px;font-size:12px" onclick="copyText('${r.data.desc.replace(/'/g, "\\'")}')">📋 复制</button>
            `;
        } else {
            card.innerHTML = `<div style="color:#C00000">#${i+1} ❌ ${r.error}</div>`;
        }
        div.appendChild(card);
    });
}

// ===== 单篇提取 =====
async function extractNote() {
    const url = document.getElementById("url-input").value.trim();
    if (!url) { showError("extract", "请输入链接"); return; }
    const btn = document.getElementById("extract-btn");
    btn.disabled = true; btn.textContent = "⏳ 提取中...";
    hideError("extract"); hideResult("extract");
    try {
        const resp = await fetch(API_BASE + "/api/extract", {
            method: "POST", headers: getHeaders(),
            body: JSON.stringify({url})
        });
        const data = await resp.json();
        if (!data.success) {
            if (data.limited) { showToast("⚠️ " + data.error); return; }
            showError("extract", data.error); return;
        }
        displayNoteResult(data.data);
        updateUsageFromServer();
    } catch(e) { showError("extract", "请求失败"); }
    finally { btn.disabled = false; btn.textContent = "🔍 提取"; }
}

function displayNoteResult(data) {
    document.getElementById("note-title").textContent = data.title || "无标题";
    document.getElementById("note-author").textContent = "👤 " + (data.author || "未知");
    document.getElementById("note-likes").textContent = "❤️ " + (data.likes || 0);
    document.getElementById("note-desc").textContent = data.desc || "暂无文案";
    const imgDiv = document.getElementById("note-images"); imgDiv.innerHTML = "";
    if (data.images && data.images.length > 0) {
        data.images.forEach(url => {
            const img = document.createElement("img");
            img.src = url; img.alt = "图片";
            img.onclick = () => window.open(url, "_blank");
            img.onerror = function() { this.style.display = "none"; };
            imgDiv.appendChild(img);
        });
    }
    showResult("extract");
}

// ===== 去水印 =====
async function removeWatermark() {
    const url = document.getElementById("wm-url-input").value.trim();
    if (!url) { showError("wm", "请输入图片链接"); return; }
    hideError("wm"); hideResult("wm");
    try {
        const resp = await fetch(API_BASE + "/api/remove_watermark", {
            method: "POST", headers: getHeaders(),
            body: JSON.stringify({image_url: url})
        });
        const data = await resp.json();
        if (!data.success) { showError("wm", data.error); return; }
        document.getElementById("wm-original").src = data.data.original;
        document.getElementById("wm-processed").src = data.data.processed;
        window._processedUrl = data.data.processed;
        showResult("wm");
        updateUsageFromServer();
    } catch(e) { showError("wm", "处理失败"); }
}

function downloadImage() {
    if (window._processedUrl) {
        const a = document.createElement("a");
        a.href = window._processedUrl;
        a.download = "processed_image.png";
        a.click();
    }
}

// ===== 文案生成 =====
async function generateCopy() {
    const topic = document.getElementById("topic-input").value.trim();
    const style = document.getElementById("style-select").value;
    if (!topic) { showError("copy", "请输入主题"); return; }
    hideError("copy"); hideResult("copy");
    try {
        const resp = await fetch(API_BASE + "/api/generate_copy", {
            method: "POST", headers: getHeaders(),
            body: JSON.stringify({topic, style})
        });
        const data = await resp.json();
        if (!data.success) { showError("copy", data.error); return; }
        document.getElementById("copy-content").textContent = data.data.join("\n\n" + "─".repeat(20) + "\n\n");
        showResult("copy");
        updateUsageFromServer();
    } catch(e) { showError("copy", "生成失败"); }
}

// ===== 记录 =====
async function loadHistory() {
    if (!USER_ID) return;
    try {
        const resp = await fetch(API_BASE + "/api/history?user_id=" + USER_ID);
        const data = await resp.json();
        if (!data.success || !data.data.length) {
            document.getElementById("history-list").innerHTML = '<p style="color:#86868b">暂无使用记录</p>';
            return;
        }
        let html = '<div style="max-height:400px;overflow-y:auto">';
        data.data.slice(0, 20).forEach(h => {
            const icon = h.tool_type === "笔记提取" ? "📝" : h.tool_type === "批量提取" ? "📑" : h.tool_type === "去水印" ? "🖼️" : "✍️";
            html += `<div style="padding:10px 14px;border-bottom:1px solid #f0f0f0;font-size:13px">
                <span>${icon} ${h.tool_type}</span>
                <span style="color:#86868b;float:right;font-size:12px">${h.created_at || ""}</span>
            </div>`;
        });
        html += "</div>";
        document.getElementById("history-list").innerHTML = html;
    } catch(e) {
        document.getElementById("history-list").innerHTML = '<p style="color:#86868b">加载失败</p>';
    }
}

async function updateUsageFromServer() {
    if (!USER_ID) return;
    try {
        const resp = await fetch(API_BASE + "/api/user/init", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({device_id: DEVICE_ID})
        });
        const data = await resp.json();
        if (data.success) updateUsage(data.user.remaining);
    } catch(e) {}
}

// ===== 复制 =====
function copyResult() {
    const text = document.getElementById("note-desc").textContent;
    navigator.clipboard.writeText(text).then(() => showToast("✅ 已复制"));
}
function copyGenerated() {
    const text = document.getElementById("copy-content").textContent;
    navigator.clipboard.writeText(text).then(() => showToast("✅ 已复制"));
}
function copyText(t) {
    navigator.clipboard.writeText(t).then(() => showToast("✅ 已复制"));
}

// ===== UI工具 =====
function showResult(p) { document.getElementById(p + "-result").classList.remove("hidden"); }
function hideResult(p) { document.getElementById(p + "-result").classList.add("hidden"); }
function showError(p, m) { const e = document.getElementById(p + "-error"); e.textContent = m; e.classList.remove("hidden"); }
function hideError(p) { document.getElementById(p + "-error").classList.add("hidden"); }

function showToast(msg) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:40px;left:50%;transform:translateX(-50%);background:#1d1d1f;color:#fff;padding:12px 24px;border-radius:12px;font-size:14px;z-index:999;box-shadow:0 4px 16px rgba(0,0,0,0.2)";
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity 0.3s"; setTimeout(() => t.remove(), 300); }, 2000);
}

// ===== 初始化 =====
initUser().then(() => {
    loadHistory();
});
