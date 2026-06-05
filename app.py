import os, re, json, time, uuid, sqlite3, hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, session, g
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "xhs.db")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== 数据库 =====
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            device_id TEXT UNIQUE,
            email TEXT,
            free_uses INTEGER DEFAULT 5,
            total_uses INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            tool_type TEXT,
            input_data TEXT,
            output_data TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            key TEXT UNIQUE,
            plan TEXT DEFAULT 'free',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.commit()
    db.close()

init_db()
app.teardown_appcontext(close_db)

# ===== 用户系统 =====
def get_or_create_user(device_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE device_id = ?", (device_id,)).fetchone()
    if not user:
        user_id = uuid.uuid4().hex[:12]
        db.execute("INSERT INTO users (id, device_id) VALUES (?, ?)", (user_id, device_id))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE device_id = ?", (device_id,)).fetchone()
    return user

def check_usage(user_id):
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    count = db.execute(
        "SELECT COUNT(*) as cnt FROM history WHERE user_id = ? AND date(created_at) = ?",
        (user_id, today)
    ).fetchone()["cnt"]
    return count

@app.route("/api/user/init", methods=["POST"])
def user_init():
    data = request.get_json()
    device_id = data.get("device_id", "")
    if not device_id:
        device_id = hashlib.md5(request.remote_addr.encode()).hexdigest()[:12]
    user = get_or_create_user(device_id)
    today_uses = check_usage(user["id"])
    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "device_id": user["device_id"],
            "email": user["email"],
            "free_uses": user["free_uses"],
            "total_uses": user["total_uses"],
            "today_uses": today_uses,
            "remaining": max(0, user["free_uses"] - today_uses)
        }
    })

@app.route("/api/user/update_email", methods=["POST"])
def update_email():
    data = request.get_json()
    user_id = data.get("user_id", "")
    email = data.get("email", "")
    if not user_id or not email:
        return jsonify({"success": False, "error": "参数错误"})
    db = get_db()
    db.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
    db.commit()
    return jsonify({"success": True})

# ===== 工具API（带用量限制） =====
def require_usage(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = request.headers.get("X-User-Id", "")
        if not user_id:
            return jsonify({"success": False, "error": "请刷新页面后重试"})
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"success": False, "error": "用户不存在"})
        today_uses = check_usage(user_id)
        if today_uses >= user["free_uses"]:
            return jsonify({"success": False, "error": f"今日免费次数已用完（{user['free_uses']}次），明天再来吧！", "limited": True})
        return fn(*args, **kwargs)
    return wrapper

def save_history(user_id, tool_type, input_data, output_data):
    db = get_db()
    hid = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO history (id, user_id, tool_type, input_data, output_data) VALUES (?, ?, ?, ?, ?)",
        (hid, user_id, tool_type, json.dumps(input_data, ensure_ascii=False), json.dumps(output_data, ensure_ascii=False))
    )
    db.execute("UPDATE users SET total_uses = total_uses + 1 WHERE id = ?", (user_id,))
    db.commit()
    return hid

# ===== 首页 =====
@app.route("/")
def index():
    return render_template("index.html")

# ===== 工具1: 笔记提取 =====
@app.route("/api/extract", methods=["POST"])
@require_usage
def extract():
    data = request.get_json()
    url = data.get("url", "").strip()
    user_id = request.headers.get("X-User-Id", "")
    if not url:
        return jsonify({"success": False, "error": "请输入小红书笔记链接"})
    try:
        result = extract_xhs_note(url)
        save_history(user_id, "笔记提取", {"url": url}, result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ===== 工具2: 去水印 =====
@app.route("/api/remove_watermark", methods=["POST"])
@require_usage
def remove_watermark():
    data = request.get_json()
    image_url = data.get("image_url", "").strip()
    user_id = request.headers.get("X-User-Id", "")
    if not image_url:
        return jsonify({"success": False, "error": "请提供图片链接"})
    try:
        result = process_image_watermark(image_url)
        save_history(user_id, "去水印", {"image_url": image_url}, result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ===== 工具3: 文案生成 =====
@app.route("/api/generate_copy", methods=["POST"])
@require_usage
def generate_copy():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    style = data.get("style", "种草")
    user_id = request.headers.get("X-User-Id", "")
    if not topic:
        return jsonify({"success": False, "error": "请输入主题"})
    copies = generate_xhs_copy(topic, style)
    save_history(user_id, "文案生成", {"topic": topic, "style": style}, {"copies": copies})
    return jsonify({"success": True, "data": copies})

# ===== 工具4: 批量提取 =====
@app.route("/api/batch_extract", methods=["POST"])
@require_usage
def batch_extract():
    data = request.get_json()
    urls = data.get("urls", [])
    user_id = request.headers.get("X-User-Id", "")
    if not urls or len(urls) > 10:
        return jsonify({"success": False, "error": "请输入1-10个链接"})
    results = []
    for url in urls:
        try:
            result = extract_xhs_note(url.strip())
            results.append({"url": url, "success": True, "data": result})
        except Exception as e:
            results.append({"url": url, "success": False, "error": str(e)})
    save_history(user_id, "批量提取", {"urls": urls}, results)
    return jsonify({"success": True, "data": results})

# ===== 历史记录 =====
@app.route("/api/history", methods=["GET"])
def get_history():
    user_id = request.args.get("user_id", "")
    if not user_id:
        return jsonify({"success": False, "error": "参数错误"})
    db = get_db()
    rows = db.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,)
    ).fetchall()
    return jsonify({
        "success": True,
        "data": [dict(r) for r in rows]
    })

# ===== 小红书内容提取 =====
def extract_xhs_note(url):
    note_id = extract_note_id(url)
    if not note_id:
        raise ValueError("无法识别笔记ID，请检查链接格式")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.xiaohongshu.com/",
        "Cookie": ""
    }
    api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    resp = requests.get(api_url, headers=headers, timeout=15)
    result = {
        "note_id": note_id,
        "title": "",
        "desc": "",
        "images": [],
        "author": "",
        "likes": 0,
        "url": api_url
    }
    pattern = r"<script>window\.__INITIAL_STATE__\s*=\s*({.*?})</script>"
    match = re.search(pattern, resp.text)
    if match:
        raw = match.group(1)
        try:
            data = json.loads(raw)
            note_data = data.get("note", {})
            if not note_data:
                for key in data.get("noteDetailMap", {}):
                    note_data = data["noteDetailMap"][key]["note"]
                    break
            if note_data:
                result["title"] = note_data.get("title", "")
                result["desc"] = note_data.get("desc", "")
                result["author"] = note_data.get("user", {}).get("nickname", "")
                result["likes"] = note_data.get("interactInfo", {}).get("likedCount", 0)
                for img in note_data.get("imageList", []):
                    url_key = img.get("urlDefault", "") or img.get("infoList", [{}])[0].get("url", "")
                    if url_key:
                        result["images"].append(f"https://ci.xiaohongshu.com/{url_key}" if not url_key.startswith("http") else url_key)
        except: pass
    if not result["desc"]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta: result["desc"] = meta.get("content", "")
        title_tag = soup.find("title")
        if title_tag: result["title"] = title_tag.text.replace(" - 小红书", "")
    return result

def extract_note_id(url):
    patterns = [
        r"xiaohongshu\.com/explore/([a-f0-9]+)",
        r"xiaohongshu\.com/discovery/item/([a-f0-9]+)",
        r"xhslink\.com/(\w+)"
    ]
    for p in patterns:
        m = re.search(p, url)
        if m: return m.group(1)
    return None

def process_image_watermark(image_url):
    import requests as req
    from io import BytesIO
    from PIL import Image
    resp = req.get(image_url, timeout=15)
    img = Image.open(BytesIO(resp.content))
    w, h = img.size
    crop_h = int(h * 0.92)
    cropped = img.crop((0, 0, w, crop_h))
    output = BytesIO()
    cropped.save(output, format="PNG", quality=95)
    output.seek(0)
    filename = f"wm_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    with open(filepath, "wb") as f:
        f.write(output.getvalue())
    return {"original": image_url, "processed": f"/uploads/{filename}", "width": w, "height": crop_h}

def generate_xhs_copy(topic, style):
    templates = {
        "种草": [
            f"不出意外的话{topic}我要用一辈子\n\n先说结论：真的好用！\n\n用了之后真的回不去了\n\n✅ 优点：\n- 效果明显\n- 性价比高\n- 包装精致\n\n#种草 #{topic}",
            f"姐妹们！{topic}真的绝了！\n\n不夸张地说，这是我今年买过最值的东西\n\n1. 质感在线\n2. 使用感满分\n3. 无限回购中\n\n冲就完了！\n\n#{topic} #好物推荐"
        ],
        "测评": [
            f"{topic}｜用了一个月来说实话\n\n✨ 优点：\n效果不错，体验感好\n\n⚠️ 槽点：\n价格小贵，不适合所有人\n\n总分：8/10\n\n#{topic} #测评",
            f"真实测评{topic}｜值不值得买？\n\n答案：看需求\n\n适合人群：预算充足、追求品质\n\n不适合：学生党\n\n#{topic} #真实测评"
        ],
        "教程": [
            f"{topic}保姆级教程｜0基础也能会\n\n步骤：\n1. 打开设置\n2. 按照步骤来\n3. 查看效果\n\n多练几次就好了\n\n#{topic} #教程 #干货"
        ]
    }
    return templates.get(style, templates["种草"])

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
