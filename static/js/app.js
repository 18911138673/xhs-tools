// ===== 笔记内容提取 =====
async function extractNote() {
    const url = document.getElementById("url-input").value.trim();
    if (!url) { showError("extract", "请输入小红书笔记链接"); return; }
    
    const btn = document.getElementById("extract-btn");
    btn.disabled = true;
    document.getElementById("extract-btn-text").classList.add("hidden");
    document.getElementById("extract-btn-loading").classList.remove("hidden");
    hideError("extract");
    hideResult("extract");
    
    try {
        const resp = await fetch("/api/extract", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url})
        });
        const data = await resp.json();
        
        if (!data.success) {
            showError("extract", data.error);
            return;
        }
        
        displayNoteResult(data.data);
    } catch (e) {
        showError("extract", "请求失败，请检查网络后重试");
    } finally {
        btn.disabled = false;
        document.getElementById("extract-btn-text").classList.remove("hidden");
        document.getElementById("extract-btn-loading").classList.add("hidden");
    }
}

function displayNoteResult(data) {
    document.getElementById("note-title").textContent = data.title || "无标题";
    document.getElementById("note-author").textContent = "👤 " + (data.author || "未知");
    document.getElementById("note-likes").textContent = "❤️ " + (data.likes || 0);
    document.getElementById("note-desc").textContent = data.desc || "暂无文案内容";
    
    const imagesDiv = document.getElementById("note-images");
    imagesDiv.innerHTML = "";
    if (data.images && data.images.length > 0) {
        data.images.forEach(url => {
            const img = document.createElement("img");
            img.src = url;
            img.alt = "笔记图片";
            img.onclick = () => window.open(url, "_blank");
            imagesDiv.appendChild(img);
        });
    }
    
    showResult("extract");
}

// ===== 去水印 =====
async function removeWatermark() {
    const url = document.getElementById("wm-url-input").value.trim();
    if (!url) { showError("wm", "请输入图片链接"); return; }
    
    hideError("wm");
    hideResult("wm");
    
    try {
        const resp = await fetch("/api/remove_watermark", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({image_url: url})
        });
        const data = await resp.json();
        
        if (!data.success) {
            showError("wm", data.error);
            return;
        }
        
        document.getElementById("wm-original").src = data.data.original;
        document.getElementById("wm-processed").src = data.data.processed;
        window._processedUrl = data.data.processed;
        showResult("wm");
    } catch (e) {
        showError("wm", "处理失败，请重试");
    }
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
    
    hideError("copy");
    hideResult("copy");
    
    try {
        const resp = await fetch("/api/generate_copy", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({topic, style})
        });
        const data = await resp.json();
        
        if (!data.success) {
            showError("copy", data.error);
            return;
        }
        
        document.getElementById("copy-content").textContent = data.data.join("\n\n——————\n\n");
        showResult("copy");
    } catch (e) {
        showError("copy", "生成失败，请重试");
    }
}

// ===== 复制 =====
function copyResult() {
    const text = document.getElementById("note-desc").textContent;
    navigator.clipboard.writeText(text).then(() => {
        showToast("✅ 文案已复制");
    });
}

function copyGenerated() {
    const text = document.getElementById("copy-content").textContent;
    navigator.clipboard.writeText(text).then(() => {
        showToast("✅ 文案已复制");
    });
}

// ===== 工具函数 =====
function showResult(prefix) {
    document.getElementById(`${prefix}-result`).classList.remove("hidden");
}
function hideResult(prefix) {
    document.getElementById(`${prefix}-result`).classList.add("hidden");
}
function showError(prefix, msg) {
    const el = document.getElementById(`${prefix}-error`);
    el.textContent = msg;
    el.classList.remove("hidden");
}
function hideError(prefix) {
    document.getElementById(`${prefix}-error`).classList.add("hidden");
}

function showToast(msg) {
    const toast = document.createElement("div");
    toast.textContent = msg;
    toast.style.cssText = `
        position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
        background: #1d1d1f; color: #fff; padding: 12px 24px;
        border-radius: 12px; font-size: 14px; z-index: 999;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        animation: fadeInUp 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transition = "opacity 0.3s";
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}
