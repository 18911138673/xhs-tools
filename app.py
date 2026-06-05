import os, re, json, time, uuid
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== 首页 =====
@app.route("/")
def index():
    return render_template("index.html")

# ===== 工具1: 笔记内容提取 =====
@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "请输入小红书笔记链接"})
    
    try:
        result = extract_xhs_note(url)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ===== 工具2: 去水印 =====
@app.route("/api/remove_watermark", methods=["POST"])
def remove_watermark():
    data = request.get_json()
    image_url = data.get("image_url", "").strip()
    if not image_url:
        return jsonify({"success": False, "error": "请提供图片链接"})
    try:
        result = process_image_watermark(image_url)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ===== 工具3: 文案生成 =====
@app.route("/api/generate_copy", methods=["POST"])
def generate_copy():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    style = data.get("style", "种草")
    if not topic:
        return jsonify({"success": False, "error": "请输入主题"})
    # 模拟生成 - 实际可用GPT API
    copies = generate_xhs_copy(topic, style)
    return jsonify({"success": True, "data": copies})

# ===== 小红书内容提取 =====
def extract_xhs_note(url):
    """从小红书链接提取笔记内容"""
    note_id = extract_note_id(url)
    if not note_id:
        raise ValueError("无法识别笔记ID，请检查链接格式")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.xiaohongshu.com/"
    }
    
    api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    
    # 使用requests获取页面（简化版，实际可能需要Playwright）
    resp = requests.get(api_url, headers=headers, timeout=15)
    
    # 从HTML中提取数据
    import re
    # 尝试提取window.__INITIAL_STATE__
    pattern = r'<script>window\.__INITIAL_STATE__\s*=\s*({.*?})</script>'
    match = re.search(pattern, resp.text)
    
    result = {
        "note_id": note_id,
        "title": "",
        "desc": "",
        "images": [],
        "author": "",
        "likes": 0,
        "url": api_url
    }
    
    if match:
        import json
        data = json.loads(match.group(1))
        note = data.get("note", {}) or data.get("noteDetailMap", {}).get(note_id, {})
        if note:
            result["title"] = note.get("title", "")
            result["desc"] = note.get("desc", "")
            result["author"] = note.get("user", {}).get("nickname", "")
            result["likes"] = note.get("interactInfo", {}).get("likedCount", 0)
            image_list = note.get("imageList", []) or note.get("imageList", [])
            for img in image_list:
                url_key = img.get("urlDefault", img.get("infoList", [{}])[0].get("url", ""))
                if url_key:
                    result["images"].append(f"https://ci.xiaohongshu.com/{url_key}" if not url_key.startswith("http") else url_key)
    
    # 如果没提取到，用BeautifulSoup获取基本信息
    if not result["desc"]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["desc"] = meta_desc.get("content", "")
        meta_title = soup.find("title")
        if meta_title:
            result["title"] = meta_title.text.replace(" - 小红书", "")
    
    return result

def extract_note_id(url):
    """从URL中提取笔记ID"""
    patterns = [
        r"xiaohongshu\.com/explore/([a-f0-9]+)",
        r"xiaohongshu\.com/discovery/item/([a-f0-9]+)",
        r"xhslink\.com/(\w+)"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

# ===== 图片去水印 =====
def process_image_watermark(image_url):
    """处理图片水印（用PIL模糊/裁剪底部水印区域）"""
    import requests
    from io import BytesIO
    from PIL import Image, ImageFilter
    
    resp = requests.get(image_url, timeout=15)
    img = Image.open(BytesIO(resp.content))
    
    # 简单去水印：裁剪底部10%区域（水印通常在右下角）
    w, h = img.size
    crop_h = int(h * 0.92)
    cropped = img.crop((0, 0, w, crop_h))
    
    output = BytesIO()
    cropped.save(output, format="PNG", quality=95)
    output.seek(0)
    
    # 保存到本地
    filename = f"wm_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(output.getvalue())
    
    return {
        "original": image_url,
        "processed": f"/uploads/{filename}",
        "width": w,
        "height": crop_h
    }

# ===== AI文案生成 =====
def generate_xhs_copy(topic, style):
    """生成小红书风格文案"""
    templates = {
        "种草": [
            f"🔥{topic}也太好用了吧！我直接回购3次！\n\n姐妹们信我，这个真的绝了！\n\n✨【使用感受】\n第一次用就被惊艳到了...\n\n✨【优点总结】\n✅ 性价比超高\n✅ 效果立竿见影\n✅ 包装也很精致\n\n#好物分享 #{topic} #必买清单",
            f"我不允许还有人不知道{topic}！\n\n用了半个月真的忍不住来安利\n\n📌 为什么推荐？\n1️⃣ 效果真的惊艳\n2️⃣ 价格也很良心\n3️⃣ 无限回购中\n\n姐妹们冲就完了！\n\n#{topic} #种草 #良心推荐"
        ],
        "测评": [
            f"{topic}真实测评｜到底值不值得买？\n\n先说结论：值得，但有前提\n\n✅ 优点：\n• 品质在线\n• 体验感好\n\n❌ 缺点：\n• 价格偏高\n• 不适合所有人\n\n总结：预算充足可入\n\n#{topic} #测评 #真实体验",
            f"深度测评{topic}｜用了一个月来说实话\n\n先说优点再说槽点\n\n💡 优点\n- 效果确实能打\n- 使用感不错\n\n⚠️ 槽点\n- 价格略贵\n- 包装一般\n\n⭐ 综合评分：8/10\n\n#{topic} #深度测评 #拔草"
        ],
        "教程": [
            f"手把手教你用{topic}｜0基础也能学会\n\n📌 准备工具：\n{topic} + 手机/电脑\n\n📌 操作步骤：\n1️⃣ 第一步：打开设置\n2️⃣ 第二步：按照提示操作\n3️⃣ 第三步：查看效果\n\n💡 小技巧：多做几次就更熟练了\n\n#{topic} #教程 #干货分享"
        ]
    }
    return templates.get(style, templates["种草"])

# ===== 文件服务 =====
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
