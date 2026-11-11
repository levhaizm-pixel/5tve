import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for,
    session, flash, send_from_directory,
    render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "5tve.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}

CATEGORIES = [
    "Eğlence", "Oyun", "Müzik", "Spor",
    "Teknoloji", "Eğitim", "Diğer"
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            UNIQUE(user_id, video_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    columns = [
        row["name"] for row in
        conn.execute("PRAGMA table_info(videos)").fetchall()
    ]

    if "category" not in columns:
        conn.execute("ALTER TABLE videos ADD COLUMN category TEXT DEFAULT 'Diğer'")

    conn.commit()
    conn.close()


init_db()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Bu işlem için giriş yapmalısın.")
            return redirect(url_for("giris"))
        return func(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_video(video_id):
    conn = db()
    video = conn.execute("""
        SELECT videos.*, users.username,
        (SELECT COUNT(*) FROM likes WHERE likes.video_id = videos.id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE comments.video_id = videos.id) AS comment_count
        FROM videos
        JOIN users ON users.id = videos.user_id
        WHERE videos.id = ?
    """, (video_id,)).fetchone()
    conn.close()
    return video


BASE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>5TVE - Video Platformu</title>
<style>
*{box-sizing:border-box}
body{
    margin:0;
    font-family:Arial,sans-serif;
    color:#fff;
    background:
      radial-gradient(ellipse at 15% 15%,#32216c 0%,transparent 35%),
      radial-gradient(ellipse at 85% 75%,#123d75 0%,transparent 35%),
      linear-gradient(135deg,#080b18,#10152b 55%,#090d1c);
    min-height:100vh;
}
body:before{
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    opacity:.12;
    background-image:
      linear-gradient(45deg,transparent 48%,#8794ff 49%,transparent 50%),
      linear-gradient(-45deg,transparent 48%,#8794ff 49%,transparent 50%);
    background-size:65px 65px;
}
nav{
    position:sticky;
    top:0;
    z-index:10;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:15px;
    flex-wrap:wrap;
    padding:16px 5%;
    background:rgba(8,11,25,.88);
    backdrop-filter:blur(15px);
    border-bottom:1px solid #30365b;
}
.logo{
    font-size:27px;
    font-weight:900;
    letter-spacing:2px;
    background:linear-gradient(90deg,#44c8ff,#a66cff);
    -webkit-background-clip:text;
    color:transparent;
}
.navlinks{
    display:flex;
    gap:9px;
    flex-wrap:wrap;
}
.navlinks a{
    color:#dce2ff;
    text-decoration:none;
    padding:11px 14px;
    border-radius:12px;
    background:#171d37;
    border:1px solid #30385f;
    transition:.2s;
}
.navlinks a:hover{
    background:#34316c;
    border-color:#8b75ff;
    transform:translateY(-2px);
}
.container{
    width:90%;
    max-width:1250px;
    margin:35px auto;
    position:relative;
}
.hero{
    padding:55px 35px;
    border:1px solid #45457e;
    border-radius:25px;
    background:linear-gradient(120deg,rgba(43,48,104,.9),rgba(18,48,87,.75));
    box-shadow:0 15px 50px #0005;
    margin-bottom:35px;
}
.hero h1{font-size:42px;margin:0 0 12px}
.hero p{color:#c5cbea;font-size:16px}
.btn{
    display:inline-block;
    background:linear-gradient(90deg,#6655ff,#249bff);
    color:white;
    padding:12px 20px;
    border:0;
    border-radius:12px;
    text-decoration:none;
    cursor:pointer;
    font-weight:bold;
}
.btn:hover{filter:brightness(1.15)}
.section-title{
    font-size:24px;
    margin:25px 0;
}
.grid{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(245px,1fr));
    gap:22px;
}
.video-card{
    overflow:hidden;
    background:#151b32;
    border:1px solid #30385b;
    border-radius:18px;
    transition:.25s;
}
.video-card:hover{
    transform:translateY(-5px);
    border-color:#8174ff;
    box-shadow:0 12px 35px #0006;
}
.thumbnail{
    height:155px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:48px;
    background:linear-gradient(135deg,#342b75,#146a9c);
}
.video-info{padding:16px}
.video-info h3{margin:0 0 10px;font-size:17px}
.video-info p{color:#aab4d5;font-size:13px}
.video-info a{color:white;text-decoration:none}
.form-box{
    max-width:600px;
    margin:35px auto;
    padding:30px;
    border-radius:22px;
    border:1px solid #414778;
    background:rgba(20,26,51,.94);
    box-shadow:0 15px 45px #0005;
}
input,textarea,select{
    width:100%;
    padding:14px;
    margin:9px 0 17px;
    background:#0c1227;
    color:white;
    border:1px solid #414b78;
    border-radius:10px;
    outline:none;
}
input:focus,textarea:focus,select:focus{border-color:#8174ff}
label{color:#d5dcff;font-weight:bold}
video{
    width:100%;
    max-height:600px;
    background:#000;
    border-radius:15px;
}
.profile-header{
    padding:35px;
    border-radius:20px;
    background:linear-gradient(120deg,#28245c,#143b65);
    margin-bottom:30px;
}
.avatar{
    width:75px;
    height:75px;
    border-radius:50%;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:28px;
    font-weight:bold;
    background:linear-gradient(135deg,#8b5cff,#27b7ff);
    margin-bottom:15px;
}
.comment{
    padding:15px;
    background:#171e38;
    border-radius:12px;
    margin:12px 0;
}
.flash{
    padding:13px;
    border-radius:10px;
    background:#34315f;
    margin-bottom:15px;
}
footer{
    text-align:center;
    color:#8995bb;
    padding:35px;
}
@media(max-width:600px){
    .hero h1{font-size:30px}
    nav{justify-content:center}
    .navlinks{justify-content:center}
}
</style>
</head>
<body>

<nav>
    <a class="logo" href="/">5TVE</a>

    <div class="navlinks">
        <a href="/">🏠 Ana Sayfa</a>
        <a href="/kesfet">🔥 Keşfet</a>
        <a href="/kategoriler">🗂️ Kategoriler</a>
        <a href="/yukle">⬆️ Yükle</a>

        {% if session.get('user_id') %}
            <a href="/profil">👤 Profil</a>
            <a href="/cikis">🚪 Çıkış</a>
        {% else %}
            <a href="/giris">🔑 Giriş</a>
            <a href="/kayit">✨ Kayıt Ol</a>
        {% endif %}
    </div>
</nav>

<div class="container">
    {% with messages = get_flashed_messages() %}
      {% for message in messages %}
        <div class="flash">{{ message }}</div>
      {% endfor %}
    {% endwith %}

    {{ content|safe }}
</div>

<footer>© 2026 5TVE · Herkes için video platformu</footer>
</body>
</html>
"""


def page(content, **kwargs):
    return render_template_string(BASE, content=render_template_string(content, **kwargs))


VIDEO_CARD = """
<div class="video-card">
    <a href="{{ url_for('izle', video_id=v['id']) }}">
        <div class="thumbnail">▶</div>
    </a>
    <div class="video-info">
        <h3><a href="{{ url_for('izle', video_id=v['id']) }}">{{ v['title'] }}</a></h3>
        <p>👤 <a href="{{ url_for('kanal', username=v['username']) }}">{{ v['username'] }}</a></p>
        <p>❤️ {{ v['like_count'] }} beğeni · 💬 {{ v['comment_count'] }} yorum</p>
        <p>🗂️ {{ v['category'] or 'Diğer' }}</p>
    </div>
</div>
"""


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    conn = db()

    if q:
        videos = conn.execute("""
            SELECT videos.*, users.username,
            (SELECT COUNT(*) FROM likes WHERE video_id=videos.id) AS like_count,
            (SELECT COUNT(*) FROM comments WHERE video_id=videos.id) AS comment_count
            FROM videos JOIN users ON users.id=videos.user_id
            WHERE videos.title LIKE ? OR videos.description LIKE ?
            ORDER BY videos.id DESC
        """, (f"%{q}%", f"%{q}%")).fetchall()
    else:
        videos = conn.execute("""
            SELECT videos.*, users.username,
            (SELECT COUNT(*) FROM likes WHERE video_id=videos.id) AS like_count,
            (SELECT COUNT(*) FROM comments WHERE video_id=videos.id) AS comment_count
            FROM videos JOIN users ON users.id=videos.user_id
            ORDER BY videos.id DESC
        """).fetchall()

    conn.close()

    cards = "".join(
        render_template_string(VIDEO_CARD, v=v) for v in videos
    )

    content = """
    <div class="hero">
        <h1>5TVE'ye Hoş Geldin! 🚀</h1>
        <p>En sevdiğin videoları keşfet, paylaş ve kendi kanalını oluştur.</p>
        <a class="btn" href="/kesfet">Videoları Keşfet →</a>
    </div>

    <form method="GET" action="/" style="display:flex;gap:10px">
        <input name="q" placeholder="Video ara..." value="{{ q }}">
        <button class="btn" style="margin:9px 0 17px">🔍 Ara</button>
    </form>

    <h2 class="section-title">🎬 Son Videolar</h2>

    {% if cards %}
        <div class="grid">{{ cards|safe }}</div>
    {% else %}
        <p>Henüz video yüklenmemiş. İlk videoyu sen yükle!</p>
    {% endif %}
    """
    return page(content, cards=cards, q=q)


@app.route("/kesfet")
def kesfet():
    conn = db()
    videos = conn.execute("""
        SELECT videos.*, users.username,
        (SELECT COUNT(*) FROM likes WHERE video_id=videos.id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE video_id=videos.id) AS comment_count
        FROM videos JOIN users ON users.id=videos.user_id
        ORDER BY videos.id DESC
    """).fetchall()
    conn.close()

    cards = "".join(render_template_string(VIDEO_CARD, v=v) for v in videos)

    return page("""
        <h1 class="section-title">🔥 Videoları Keşfet</h1>
        {% if cards %}
          <div class="grid">{{ cards|safe }}</div>
        {% else %}
          <p>Henüz keşfedilecek video yok.</p>
        {% endif %}
    """, cards=cards)


@app.route("/kategoriler")
def kategoriler():
    return page("""
        <h1 class="section-title">🗂️ Kategoriler</h1>
        <div class="grid">
        {% for c in categories %}
            <a class="video-card" style="padding:35px;text-align:center;color:white;text-decoration:none"
               href="{{ url_for('kategori', category=c) }}">
                <div style="font-size:35px">🎥</div>
                <h2>{{ c }}</h2>
                <p>Videoları görüntüle →</p>
            </a>
        {% endfor %}
        </div>
    """, categories=CATEGORIES)


@app.route("/kategori/<category>")
def kategori(category):
    conn = db()
    videos = conn.execute("""
        SELECT videos.*, users.username,
        (SELECT COUNT(*) FROM likes WHERE video_id=videos.id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE video_id=videos.id) AS comment_count
        FROM videos JOIN users ON users.id=videos.user_id
        WHERE videos.category=?
        ORDER BY videos.id DESC
    """, (category,)).fetchall()
    conn.close()

    cards = "".join(render_template_string(VIDEO_CARD, v=v) for v in videos)

    return page("""
        <h1 class="section-title">🗂️ {{ category }}</h1>
        {% if cards %}
          <div class="grid">{{ cards|safe }}</div>
        {% else %}
          <p>Bu kategoride henüz video yok.</p>
        {% endif %}
    """, category=category, cards=cards)


@app.route("/yukle", methods=["GET", "POST"])
@login_required
def yukle():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "Diğer")
        file = request.files.get("video")

        if not title or not file or not file.filename:
            flash("Başlık ve video dosyası gerekli.")
            return redirect(url_for("yukle"))

        if not allowed_file(file.filename):
            flash("MP4, WEBM, MOV veya M4V dosyası yükleyebilirsin.")
            return redirect(url_for("yukle"))

        if category not in CATEGORIES:
            category = "Diğer"

        filename = secure_filename(file.filename)
        unique_name = secrets.token_hex(8) + "_" + filename
        file.save(os.path.join(UPLOAD_FOLDER, unique_name))

        conn = db()
        conn.execute("""
            INSERT INTO videos (title, description, filename, user_id, category)
            VALUES (?, ?, ?, ?, ?)
        """, (title, description, unique_name, session["user_id"], category))
        conn.commit()
        conn.close()

        flash("Videon başarıyla yüklendi!")
        return redirect(url_for("profil"))

    return page("""
        <div class="form-box">
            <h1>⬆️ Video Yükle</h1>
            <p>Videonu 5TVE topluluğuyla paylaş.</p>

            <form method="POST" enctype="multipart/form-data">
                <label>Video Başlığı</label>
                <input name="title" maxlength="100" required placeholder="Videonun adı">

                <label>Açıklama</label>
                <textarea name="description" rows="4" placeholder="Videonu açıkla..."></textarea>

                <label>Kategori</label>
                <select name="category">
                    {% for c in categories %}
                        <option value="{{ c }}">{{ c }}</option>
                    {% endfor %}
                </select>

                <label>Video Dosyası</label>
                <input type="file" name="video" accept="video/mp4,video/webm,video/quicktime" required>

                <button class="btn" style="width:100%">🚀 Videoyu Yayınla</button>
            </form>
            <p>En fazla 200 MB. MP4, WEBM, MOV ve M4V desteklenir.</p>
        </div>
    """, categories=CATEGORIES)


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(password) < 6:
            flash("Kullanıcı adı en az 3, şifre en az 6 karakter olmalı.")
            return redirect(url_for("kayit"))

        conn = db()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Bu kullanıcı adı zaten alınmış.")
            return redirect(url_for("kayit"))

        user = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        conn.close()

        session["user_id"] = user["id"]
        session["username"] = username
        return redirect(url_for("index"))

    return page("""
        <div class="form-box">
            <h1>✨ Hesap Oluştur</h1>
            <form method="POST">
                <label>Kullanıcı Adı</label>
                <input name="username" required minlength="3">
                <label>Şifre</label>
                <input type="password" name="password" required minlength="6">
                <button class="btn" style="width:100%">Kayıt Ol</button>
            </form>
            <p>Zaten hesabın var mı? <a href="/giris">Giriş yap</a></p>
        </div>
    """)


@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))

        flash("Kullanıcı adı veya şifre yanlış.")
        return redirect(url_for("giris"))

    return page("""
        <div class="form-box">
            <h1>🔑 Giriş Yap</h1>
            <form method="POST">
                <label>Kullanıcı Adı</label>
                <input name="username" required>
                <label>Şifre</label>
                <input type="password" name="password" required>
                <button class="btn" style="width:100%">Giriş Yap</button>
            </form>
            <p>Hesabın yok mu? <a href="/kayit">Kayıt ol</a></p>
        </div>
    """)


@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for("index"))


@app.route("/profil")
@login_required
def profil():
    return redirect(url_for("kanal", username=session["username"]))


@app.route("/kanal/<username>")
def kanal(username):
    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        abort(404)

    videos = conn.execute("""
        SELECT videos.*, users.username,
        (SELECT COUNT(*) FROM likes WHERE video_id=videos.id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE video_id=videos.id) AS comment_count
        FROM videos JOIN users ON users.id=videos.user_id
        WHERE videos.user_id=?
        ORDER BY videos.id DESC
    """, (user["id"],)).fetchall()
    conn.close()

    cards = "".join(render_template_string(VIDEO_CARD, v=v) for v in videos)
    is_owner = session.get("user_id") == user["id"]

    return page("""
        <div class="profile-header">
            <div class="avatar">{{ username[0]|upper }}</div>
            <h1>{{ username }}</h1>
            <p>5TVE Kanalı</p>
            {% if is_owner %}
                <a href="/yukle" class="btn">⬆️ Video Yükle</a>
            {% endif %}
        </div>

        <h2 class="section-title">🎬 Kanal Videoları</h2>
        {% if cards %}
            <div class="grid">{{ cards|safe }}</div>
        {% else %}
            <p>Bu kanalda henüz video yok.</p>
        {% endif %}
    """, username=username, cards=cards, is_owner=is_owner)


@app.route("/izle/<int:video_id>")
def izle(video_id):
    video = get_video(video_id)
    if not video:
        abort(404)

    conn = db()
    comments = conn.execute("""
        SELECT comments.*, users.username
        FROM comments JOIN users ON users.id=comments.user_id
        WHERE comments.video_id=?
        ORDER BY comments.id DESC
    """, (video_id,)).fetchall()

    liked = False
    if session.get("user_id"):
        liked = conn.execute(
            "SELECT id FROM likes WHERE user_id=? AND video_id=?",
            (session["user_id"], video_id)
        ).fetchone() is not None
    conn.close()

    return page("""
        <div class="form-box" style="max-width:950px">
            <video controls playsinline>
                <source src="{{ url_for('video_file', filename=video['filename']) }}">
            </video>

            <h1>{{ video['title'] }}</h1>
            <p>
                👤 <a href="{{ url_for('kanal', username=video['username']) }}">
                {{ video['username'] }}</a>
            </p>
            <p>{{ video['description'] or '' }}</p>
            <p>🗂️ {{ video['category'] or 'Diğer' }}</p>
            <p>❤️ {{ video['like_count'] }} beğeni</p>

            {% if session.get('user_id') %}
                <form method="POST" action="{{ url_for('begeni', video_id=video['id']) }}">
                    <button class="btn">{{ '❤️ Beğeniyi Geri Al' if liked else '🤍 Beğen' }}</button>
                </form>

                <form method="POST" action="{{ url_for('yorum', video_id=video['id']) }}">
                    <label>Yorum Yap</label>
                    <textarea name="content" required maxlength="1000" placeholder="Yorumunu yaz..."></textarea>
                    <button class="btn">Yorumu Gönder</button>
                </form>
            {% else %}
                <p>Beğenmek ve yorum yapmak için <a href="/giris">giriş yap.</a></p>
            {% endif %}

            <h2>💬 Yorumlar</h2>
            {% for c in comments %}
                <div class="comment">
                    <b>{{ c['username'] }}</b>
                    <p>{{ c['content'] }}</p>
                    <small>{{ c['created_at'] }}</small>
                </div>
            {% else %}
                <p>Henüz yorum yok.</p>
            {% endfor %}
        </div>
    """, video=video, comments=comments, liked=liked)


@app.route("/begeni/<int:video_id>", methods=["POST"])
@login_required
def begeni(video_id):
    conn = db()
    exists = conn.execute(
        "SELECT id FROM likes WHERE user_id=? AND video_id=?",
        (session["user_id"], video_id)
    ).fetchone()

    if exists:
        conn.execute(
            "DELETE FROM likes WHERE user_id=? AND video_id=?",
            (session["user_id"], video_id)
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO likes (user_id, video_id) VALUES (?, ?)",
            (session["user_id"], video_id)
        )

    conn.commit()
    conn.close()
    return redirect(url_for("izle", video_id=video_id))


@app.route("/yorum/<int:video_id>", methods=["POST"])
@login_required
def yorum(video_id):
    content = request.form.get("content", "").strip()

    if content:
        conn = db()
        conn.execute(
            "INSERT INTO comments (video_id, user_id, content) VALUES (?, ?, ?)",
            (video_id, session["user_id"], content[:1000])
        )
        conn.commit()
        conn.close()

    return redirect(url_for("izle", video_id=video_id))


@app.route("/video/<filename>")
def video_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.errorhandler(413)
def too_large(error):
    return "Video çok büyük! En fazla 200 MB yükleyebilirsin.", 413


if __name__ == "__main__":
    app.run(debug=True)
