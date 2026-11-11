
import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    flash, send_from_directory, render_template_string,
    abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# =========================================================
# AYARLAR
# =========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROFILE_FOLDER = os.path.join(UPLOAD_FOLDER, "profiles")
DATABASE = os.path.join(BASE_DIR, "5tve.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


# =========================================================
# VERİTABANI
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_image TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            category TEXT DEFAULT 'Genel',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            UNIQUE(user_id, video_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subscriber_id, channel_id),
            CHECK(subscriber_id != channel_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Eski veritabanlarına eksik sütunları ekle.
    user_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "profile_image" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")

    video_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(videos)").fetchall()
    ]

    if "category" not in video_columns:
        conn.execute(
            "ALTER TABLE videos ADD COLUMN category TEXT DEFAULT 'Genel'"
        )

    conn.commit()
    conn.close()


init_db()


# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Bu işlem için giriş yapmalısın.")
            return redirect(url_for("giris"))
        return func(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


def allowed_file(filename, extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in extensions
    )


def subscriber_count(user_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM subscriptions WHERE channel_id = ?",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def is_subscribed(subscriber_id, channel_id):
    conn = get_db()
    result = conn.execute("""
        SELECT id FROM subscriptions
        WHERE subscriber_id = ? AND channel_id = ?
    """, (subscriber_id, channel_id)).fetchone()
    conn.close()
    return result is not None


def unread_count(user_id):
    conn = get_db()
    count = conn.execute("""
        SELECT COUNT(*) FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()[0]
    conn.close()
    return count


# =========================================================
# TASARIM
# =========================================================

BASE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - 5TVE</title>
<style>
*{box-sizing:border-box}
body{
    margin:0;
    background:#080b16;
    color:#f5f5ff;
    font-family:Arial,sans-serif;
}
nav{
    background:#10152a;
    border-bottom:1px solid #252b49;
    padding:16px 5%;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:15px;
    flex-wrap:wrap;
}
.logo{
    font-size:28px;
    font-weight:900;
    color:#a78bfa;
    text-decoration:none;
}
.navlinks{
    display:flex;
    gap:16px;
    flex-wrap:wrap;
    align-items:center;
}
a{color:#c4b5fd;text-decoration:none}
a:hover{color:white}
.navlinks a{font-size:14px}
.container{max-width:1150px;margin:30px auto;padding:0 18px}
h1,h2,h3{color:white}
input,textarea,select{
    width:100%;
    padding:12px;
    margin:8px 0;
    border:1px solid #343b61;
    border-radius:9px;
    background:#11172d;
    color:white;
}
button,.btn{
    display:inline-block;
    padding:11px 17px;
    background:linear-gradient(100deg,#6d5dfc,#a855f7);
    color:white;
    border:0;
    border-radius:9px;
    cursor:pointer;
    font-weight:bold;
}
button:hover,.btn:hover{opacity:.85;color:white}
.grid{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
    gap:20px;
}
.card{
    background:#11172a;
    border:1px solid #252d4b;
    border-radius:14px;
    overflow:hidden;
    padding:14px;
}
.card video,.thumb{
    width:100%;
    border-radius:10px;
}
.card h3{margin-bottom:7px}
.muted{color:#9ca3bd;font-size:13px}
.panel{
    background:#11172a;
    border:1px solid #293052;
    border-radius:15px;
    padding:22px;
    margin-bottom:20px;
}
.profile{
    width:95px;height:95px;
    border-radius:50%;
    object-fit:cover;
    background:#6555d9;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    font-size:38px;
    font-weight:bold;
}
.avatar-small{
    width:38px;height:38px;
    border-radius:50%;
    object-fit:cover;
    vertical-align:middle;
}
.flash{
    background:#28234c;
    border:1px solid #6854ce;
    padding:12px;
    border-radius:9px;
    margin-bottom:12px;
}
form{margin:0}
.inline{display:inline-block}
footer{
    text-align:center;
    color:#777f9f;
    padding:35px;
}
@media(max-width:600px){
    nav{align-items:flex-start}
    .navlinks{gap:11px}
}
</style>
</head>
<body>

<nav>
    <a class="logo" href="{{ url_for('home') }}">5TVE</a>
    <div class="navlinks">
        <a href="{{ url_for('home') }}">Ana Sayfa</a>
        <a href="{{ url_for('kesfet') }}">Keşfet</a>
        <a href="{{ url_for('kategoriler') }}">Kategoriler</a>
        {% if user %}
            <a href="{{ url_for('yukle') }}">＋ Yükle</a>
            <a href="{{ url_for('abonelikler') }}">⭐ Aboneliklerim</a>
            <a href="{{ url_for('bildirimler') }}">
                🔔 Bildirimler{% if unread %} ({{ unread }}){% endif %}
            </a>
            <a href="{{ url_for('profil') }}">Profil</a>
            <a href="{{ url_for('cikis') }}">Çıkış</a>
        {% else %}
            <a href="{{ url_for('giris') }}">Giriş</a>
            <a href="{{ url_for('kayit') }}">Kayıt Ol</a>
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

<footer>5TVE © 2026 - Video paylaşım platformu</footer>
</body>
</html>
"""


def page(title, template, **kwargs):
    user = current_user()
    unread = unread_count(user["id"]) if user else 0
    content = render_template_string(
        template,
        user=user,
        unread=unread,
        **kwargs
    )
    return render_template_string(
        BASE,
        title=title,
        content=content,
        user=user,
        unread=unread
    )


VIDEO_CARD = """
<div class="card">
    <a href="{{ url_for('izle', video_id=v.id) }}">
        <video class="thumb" preload="metadata">
            <source src="{{ url_for('video_file', filename=v.filename) }}">
        </video>
        <h3>{{ v.title }}</h3>
    </a>
    <p class="muted">
        <a href="{{ url_for('kanal', username=v.username) }}">
            {% if v.profile_image %}
                <img class="avatar-small"
                src="{{ url_for('profile_file', filename=v.profile_image) }}">
            {% endif %}
            {{ v.username }}
        </a>
        · {{ v.category or 'Genel' }}
    </p>
    <p class="muted">{{ v.created_at }}</p>
</div>
"""


# =========================================================
# ANA SAYFA VE KEŞFET
# =========================================================

def get_videos(search=None, category=None):
    conn = get_db()

    sql = """
        SELECT videos.*, users.username, users.profile_image
        FROM videos
        JOIN users ON users.id = videos.user_id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (videos.title LIKE ? OR videos.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if category:
        sql += " AND videos.category = ?"
        params.append(category)

    sql += " ORDER BY videos.id DESC"

    videos = conn.execute(sql, params).fetchall()
    conn.close()
    return videos


@app.route("/")
def home():
    videos = get_videos(request.args.get("q"))
    return page("Ana Sayfa", """
    <h1>5TVE'ye Hoş Geldin!</h1>
    <p class="muted">Videoları keşfet, paylaş ve kanallara abone ol.</p>

    <form method="GET">
        <input name="q" placeholder="Video ara..."
        value="{{ request.args.get('q','') }}">
        <button>Ara</button>
    </form>

    <h2>Son Videolar</h2>
    <div class="grid">
        {% for v in videos %}
            """ + VIDEO_CARD + """
        {% else %}
            <p>Henüz video yüklenmemiş.</p>
        {% endfor %}
    </div>
    """, videos=videos)


@app.route("/kesfet")
def kesfet():
    videos = get_videos()
    return page("Keşfet", """
    <h1>Keşfet</h1>
    <div class="grid">
        {% for v in videos %}
            """ + VIDEO_CARD + """
        {% else %}
            <p>Henüz video yok.</p>
        {% endfor %}
    </div>
    """, videos=videos)


@app.route("/kategoriler")
def kategoriler():
    conn = get_db()
    categories = conn.execute("""
        SELECT DISTINCT category FROM videos
        WHERE category IS NOT NULL AND category != ''
        ORDER BY category
    """).fetchall()
    conn.close()

    return page("Kategoriler", """
    <h1>Kategoriler</h1>
    <div class="grid">
        {% for c in categories %}
            <a class="card"
            href="{{ url_for('kategori', category=c.category) }}">
                <h3>{{ c.category }}</h3>
                <p class="muted">Videoları görüntüle</p>
            </a>
        {% else %}
            <p>Henüz kategori bulunmuyor.</p>
        {% endfor %}
    </div>
    """, categories=categories)


@app.route("/kategori/<category>")
def kategori(category):
    videos = get_videos(category=category)
    return page(category, """
    <h1>{{ category }}</h1>
    <div class="grid">
        {% for v in videos %}
            """ + VIDEO_CARD + """
        {% else %}
            <p>Bu kategoride video yok.</p>
        {% endfor %}
    </div>
    """, videos=videos, category=category)


# =========================================================
# KAYIT / GİRİŞ / ÇIKIŞ
# =========================================================

@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(password) < 6:
            flash("Kullanıcı adı en az 3, şifre en az 6 karakter olmalı.")
            return redirect(url_for("kayit"))

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (username, password)
                VALUES (?, ?)
            """, (username, generate_password_hash(password)))
            conn.commit()
            flash("Hesabın oluşturuldu. Giriş yapabilirsin.")
            return redirect(url_for("giris"))
        except sqlite3.IntegrityError:
            flash("Bu kullanıcı adı zaten alınmış.")
        finally:
            conn.close()

    return page("Kayıt Ol", """
    <div class="panel">
        <h1>Hesap Oluştur</h1>
        <form method="POST">
            <input name="username" placeholder="Kullanıcı adı" required>
            <input type="password" name="password"
            placeholder="Şifre" required>
            <button type="submit">Kayıt Ol</button>
        </form>
    </div>
    """)


@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        account = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if account and check_password_hash(account["password"], password):
            session.clear()
            session["user_id"] = account["id"]
            flash("Giriş başarılı!")
            return redirect(url_for("home"))

        flash("Kullanıcı adı veya şifre yanlış.")

    return page("Giriş", """
    <div class="panel">
        <h1>Giriş Yap</h1>
        <form method="POST">
            <input name="username" placeholder="Kullanıcı adı" required>
            <input type="password" name="password"
            placeholder="Şifre" required>
            <button type="submit">Giriş Yap</button>
        </form>
    </div>
    """)


@app.route("/cikis")
def cikis():
    session.clear()
    flash("Çıkış yapıldı.")
    return redirect(url_for("home"))


# =========================================================
# PROFİL VE PROFİL FOTOĞRAFI
# =========================================================

@app.route("/profil")
@login_required
def profil():
    user = current_user()
    return redirect(url_for("kanal", username=user["username"]))


@app.route("/profil-fotografi", methods=["POST"])
@login_required
def profil_fotografi():
    file = request.files.get("profile_image")

    if not file or not file.filename:
        flash("Bir fotoğraf seçmelisin.")
        return redirect(url_for("profil"))

    if not allowed_file(file.filename, IMAGE_EXTENSIONS):
        flash("Sadece JPG, JPEG, PNG veya WEBP yükleyebilirsin.")
        return redirect(url_for("profil"))

    filename = secrets.token_hex(16) + "." + file.filename.rsplit(".", 1)[1].lower()
    file.save(os.path.join(PROFILE_FOLDER, filename))

    conn = get_db()
    conn.execute(
        "UPDATE users SET profile_image = ? WHERE id = ?",
        (filename, session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("Profil fotoğrafın güncellendi!")
    return redirect(url_for("profil"))


@app.route("/profil-resmi/<filename>")
def profile_file(filename):
    return send_from_directory(PROFILE_FOLDER, filename)


@app.route("/kanal/<username>")
def kanal(username):
    conn = get_db()

    channel = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not channel:
        conn.close()
        abort(404)

    videos = conn.execute("""
        SELECT videos.*, users.username, users.profile_image
        FROM videos
        JOIN users ON users.id = videos.user_id
        WHERE videos.user_id = ?
        ORDER BY videos.id DESC
    """, (channel["id"],)).fetchall()

    count = conn.execute("""
        SELECT COUNT(*) FROM subscriptions WHERE channel_id = ?
    """, (channel["id"],)).fetchone()[0]

    video_count = len(videos)
    conn.close()

    owner = (
        session.get("user_id") == channel["id"]
    )

    subscribed = False
    if session.get("user_id") and not owner:
        subscribed = is_subscribed(
            session["user_id"], channel["id"]
        )

    return page("Kanal", """
    <div class="panel">
        <div>
            {% if channel.profile_image %}
                <img class="profile"
                src="{{ url_for('profile_file', filename=channel.profile_image) }}">
            {% else %}
                <div class="profile">{{ channel.username[0]|upper }}</div>
            {% endif %}
        </div>

        <h1>{{ channel.username }}</h1>
        <p class="muted">
            ⭐ {{ count }} abone · {{ video_count }} video
        </p>

        {% if owner %}
            <h3>Profil Fotoğrafını Değiştir</h3>
            <form method="POST" action="{{ url_for('profil_fotografi') }}"
            enctype="multipart/form-data">
                <input type="file" name="profile_image"
                accept=".jpg,.jpeg,.png,.webp" required>
                <button>Fotoğrafı Yükle</button>
            </form>
        {% elif user %}
            <form method="POST"
            action="{{ url_for('abone', channel_id=channel.id) }}">
                {% if subscribed %}
                    <button>✓ Abonesin · Abonelikten Çık</button>
                {% else %}
                    <button>⭐ Abone Ol</button>
                {% endif %}
            </form>
        {% else %}
            <a class="btn" href="{{ url_for('giris') }}">Abone Olmak İçin Giriş Yap</a>
        {% endif %}
    </div>

    <h2>{{ channel.username }} kanalının videoları</h2>
    <div class="grid">
        {% for v in videos %}
            """ + VIDEO_CARD + """
        {% else %}
            <p>Bu kanalda henüz video yok.</p>
        {% endfor %}
    </div>
    """,
    channel=channel,
    videos=videos,
    count=count,
    video_count=video_count,
    owner=owner,
    subscribed=subscribed)


# =========================================================
# ABONELİK SİSTEMİ
# =========================================================

@app.route("/abone/<int:channel_id>", methods=["POST"])
@login_required
def abone(channel_id):
    if channel_id == session["user_id"]:
        flash("Kendi kanalına abone olamazsın.")
        return redirect(url_for("profil"))

    conn = get_db()

    channel = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (channel_id,)
    ).fetchone()

    if not channel:
        conn.close()
        abort(404)

    existing = conn.execute("""
        SELECT id FROM subscriptions
        WHERE subscriber_id = ? AND channel_id = ?
    """, (session["user_id"], channel_id)).fetchone()

    if existing:
        conn.execute("""
            DELETE FROM subscriptions
            WHERE subscriber_id = ? AND channel_id = ?
        """, (session["user_id"], channel_id))
        flash("Abonelikten çıktın.")
    else:
        conn.execute("""
            INSERT INTO subscriptions (subscriber_id, channel_id)
            VALUES (?, ?)
        """, (session["user_id"], channel_id))
        flash("Kanala abone oldun!")

    conn.commit()
    conn.close()

    return redirect(url_for("kanal", username=channel["username"]))


@app.route("/abonelikler")
@login_required
def abonelikler():
    conn = get_db()

    channels = conn.execute("""
        SELECT
            users.id,
            users.username,
            users.profile_image,
            (SELECT COUNT(*) FROM subscriptions s2
             WHERE s2.channel_id = users.id) AS subscribers,
            (SELECT COUNT(*) FROM videos v
             WHERE v.user_id = users.id) AS video_count
        FROM subscriptions
        JOIN users ON users.id = subscriptions.channel_id
        WHERE subscriptions.subscriber_id = ?
        ORDER BY subscriptions.id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return page("Aboneliklerim", """
    <h1>⭐ Aboneliklerim</h1>
    <div class="grid">
        {% for c in channels %}
            <div class="card">
                <a href="{{ url_for('kanal', username=c.username) }}">
                    {% if c.profile_image %}
                        <img class="profile"
                        src="{{ url_for('profile_file', filename=c.profile_image) }}">
                    {% else %}
                        <div class="profile">{{ c.username[0]|upper }}</div>
                    {% endif %}
                    <h3>{{ c.username }}</h3>
                </a>
                <p class="muted">
                    {{ c.subscribers }} abone · {{ c.video_count }} video
                </p>
            </div>
        {% else %}
            <p>Henüz bir kanala abone değilsin.</p>
        {% endfor %}
    </div>
    """, channels=channels)


# =========================================================
# BİLDİRİMLER
# =========================================================

@app.route("/bildirimler")
@login_required
def bildirimler():
    conn = get_db()

    notifications = conn.execute("""
        SELECT
            notifications.*,
            users.username,
            videos.title
        FROM notifications
        JOIN users ON users.id = notifications.actor_id
        LEFT JOIN videos ON videos.id = notifications.video_id
        WHERE notifications.user_id = ?
        ORDER BY notifications.id DESC
    """, (session["user_id"],)).fetchall()

    conn.execute("""
        UPDATE notifications SET is_read = 1
        WHERE user_id = ?
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return page("Bildirimler", """
    <h1>🔔 Bildirimler</h1>
    {% for n in notifications %}
        <div class="panel">
            <a href="{{ url_for('kanal', username=n.username) }}">
                <b>{{ n.username }}</b>
            </a>
            yeni bir video yükledi:
            {% if n.video_id %}
                <a href="{{ url_for('izle', video_id=n.video_id) }}">
                    {{ n.title or 'Video' }}
                </a>
            {% else %}
                {{ n.title or 'Video' }}
            {% endif %}
            <p class="muted">{{ n.created_at }}</p>
        </div>
    {% else %}
        <p>Henüz bildirimin yok.</p>
    {% endfor %}
    """, notifications=notifications)


# =========================================================
# VİDEO YÜKLEME
# =========================================================

@app.route("/yukle", methods=["GET", "POST"])
@login_required
def yukle():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "Genel").strip()
        file = request.files.get("video")

        if not title or not file or not file.filename:
            flash("Başlık ve video dosyası gerekli.")
            return redirect(url_for("yukle"))

        if not allowed_file(file.filename, VIDEO_EXTENSIONS):
            flash("Sadece MP4, WEBM, MOV veya M4V yükleyebilirsin.")
            return redirect(url_for("yukle"))

        filename = secrets.token_hex(16) + "." + file.filename.rsplit(".", 1)[1].lower()
        file.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = get_db()
        conn.execute("""
            INSERT INTO videos
            (title, description, filename, user_id, category)
            VALUES (?, ?, ?, ?, ?)
        """, (
            title,
            description,
            filename,
            session["user_id"],
            category or "Genel"
        ))

        video_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        uploader = conn.execute(
            "SELECT username FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        subscribers = conn.execute("""
            SELECT subscriber_id FROM subscriptions
            WHERE channel_id = ?
        """, (session["user_id"],)).fetchall()

        message = f"{uploader['username']} yeni bir video yükledi: {title}"

        for subscriber in subscribers:
            conn.execute("""
                INSERT INTO notifications
                (user_id, actor_id, video_id, message)
                VALUES (?, ?, ?, ?)
            """, (
                subscriber["subscriber_id"],
                session["user_id"],
                video_id,
                message
            ))

        conn.commit()
        conn.close()

        flash("Videon başarıyla yüklendi!")
        return redirect(url_for("izle", video_id=video_id))

    return page("Video Yükle", """
    <div class="panel">
        <h1>＋ Video Yükle</h1>
        <form method="POST" enctype="multipart/form-data">
            <input name="title" placeholder="Video başlığı" required>
            <textarea name="description"
            placeholder="Video açıklaması"></textarea>

            <select name="category">
                <option>Genel</option>
                <option>Eğlence</option>
                <option>Oyun</option>
                <option>Müzik</option>
                <option>Eğitim</option>
                <option>Spor</option>
                <option>Diğer</option>
            </select>

            <label>Video dosyası (MP4, WEBM, MOV, M4V)</label>
            <input type="file" name="video"
            accept=".mp4,.webm,.mov,.m4v" required>

            <button type="submit">Videoyu Yükle</button>
        </form>
    </div>
    """)


# =========================================================
# VİDEO İZLEME
# =========================================================

@app.route("/izle/<int:video_id>")
def izle(video_id):
    conn = get_db()

    video = conn.execute("""
        SELECT videos.*, users.username, users.profile_image
        FROM videos
        JOIN users ON users.id = videos.user_id
        WHERE videos.id = ?
    """, (video_id,)).fetchone()

    if not video:
        conn.close()
        abort(404)

    comments = conn.execute("""
        SELECT comments.*, users.username, users.profile_image
        FROM comments
        JOIN users ON users.id = comments.user_id
        WHERE comments.video_id = ?
        ORDER BY comments.id DESC
    """, (video_id,)).fetchall()

    likes = conn.execute(
        "SELECT COUNT(*) FROM likes WHERE video_id = ?",
        (video_id,)
    ).fetchone()[0]

    liked = False
    if session.get("user_id"):
        liked = conn.execute("""
            SELECT id FROM likes
            WHERE user_id = ? AND video_id = ?
        """, (session["user_id"], video_id)).fetchone() is not None

    conn.close()

    return page(video["title"], """
    <div class="panel">
        <video controls autoplay style="width:100%;max-height:600px"
        src="{{ url_for('video_file', filename=video.filename) }}">
        </video>

        <h1>{{ video.title }}</h1>
        <p>{{ video.description or '' }}</p>

        <p>
            <a href="{{ url_for('kanal', username=video.username) }}">
                {% if video.profile_image %}
                    <img class="avatar-small"
                    src="{{ url_for('profile_file', filename=video.profile_image) }}">
                {% endif %}
                {{ video.username }}
            </a>
        </p>

        <p class="muted">
            {{ video.category }} · {{ video.created_at }}
        </p>

        <p>❤️ {{ likes }} beğeni</p>

        {% if user %}
            <form class="inline" method="POST"
            action="{{ url_for('begeni', video_id=video.id) }}">
                <button>
                    {% if liked %}❤️ Beğeniyi Geri Al{% else %}🤍 Beğen{% endif %}
                </button>
            </form>
        {% else %}
            <a class="btn" href="{{ url_for('giris') }}">Beğenmek için giriş yap</a>
        {% endif %}
    </div>

    <div class="panel">
        <h2>Yorumlar</h2>
        {% if user %}
            <form method="POST"
            action="{{ url_for('yorum', video_id=video.id) }}">
                <textarea name="content"
                placeholder="Yorum yaz..." required></textarea>
                <button>Yorum Gönder</button>
            </form>
        {% else %}
            <p>Yorum yapmak için giriş yapmalısın.</p>
        {% endif %}

        {% for c in comments %}
            <div class="panel">
                <b>
                    <a href="{{ url_for('kanal', username=c.username) }}">
                        {{ c.username }}
                    </a>
                </b>
                <p>{{ c.content }}</p>
                <span class="muted">{{ c.created_at }}</span>
            </div>
        {% else %}
            <p>Henüz yorum yok.</p>
        {% endfor %}
    </div>
    """,
    video=video,
    comments=comments,
    likes=likes,
    liked=liked)


@app.route("/begeni/<int:video_id>", methods=["POST"])
@login_required
def begeni(video_id):
    conn = get_db()

    video = conn.execute(
        "SELECT id FROM videos WHERE id = ?",
        (video_id,)
    ).fetchone()

    if not video:
        conn.close()
        abort(404)

    existing = conn.execute("""
        SELECT id FROM likes
        WHERE user_id = ? AND video_id = ?
    """, (session["user_id"], video_id)).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM likes WHERE id = ?",
            (existing["id"],)
        )
    else:
        conn.execute("""
            INSERT OR IGNORE INTO likes (user_id, video_id)
            VALUES (?, ?)
        """, (session["user_id"], video_id))

    conn.commit()
    conn.close()

    return redirect(url_for("izle", video_id=video_id))


@app.route("/yorum/<int:video_id>", methods=["POST"])
@login_required
def yorum(video_id):
    content = request.form.get("content", "").strip()

    if not content:
        flash("Yorum boş olamaz.")
        return redirect(url_for("izle", video_id=video_id))

    conn = get_db()

    video = conn.execute(
        "SELECT id FROM videos WHERE id = ?",
        (video_id,)
    ).fetchone()

    if not video:
        conn.close()
        abort(404)

    conn.execute("""
        INSERT INTO comments (user_id, video_id, content)
        VALUES (?, ?, ?)
    """, (session["user_id"], video_id, content))

    conn.commit()
    conn.close()

    return redirect(url_for("izle", video_id=video_id))


# =========================================================
# DOSYA SERVİSİ
# =========================================================

@app.route("/video/<filename>")
def video_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.errorhandler(413)
def file_too_large(error):
    return "Dosya çok büyük. En fazla 200 MB yükleyebilirsin.", 413


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
