
import os
import sqlite3
import uuid
from functools import wraps

from flask import (
    Flask, request, redirect, url_for,
    session, render_template_string, send_from_directory,
    abort, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "5TVE-change-this-secret")

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE = os.path.join(BASE_DIR, "5tve.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "mp4", "webm", "mov", "m4v"
}


def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        owner TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        UNIQUE(video_id, username)
    );

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()
    con.close()


init_db()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


STYLE = """
* { box-sizing:border-box; }
body {
    margin:0;
    background:#101010;
    color:white;
    font-family:Arial,sans-serif;
}
header {
    background:#191919;
    padding:18px 5%;
    display:flex;
    justify-content:space-between;
    align-items:center;
    flex-wrap:wrap;
    gap:12px;
}
.logo {
    color:#ff3030;
    font-size:30px;
    font-weight:bold;
    text-decoration:none;
}
a { color:white; text-decoration:none; }
nav { display:flex; gap:15px; align-items:center; flex-wrap:wrap; }
main { padding:25px 5%; }
button,.btn {
    background:#ff3030;
    color:white;
    border:0;
    padding:11px 17px;
    border-radius:7px;
    cursor:pointer;
}
button:hover,.btn:hover { background:#d82020; }
input {
    padding:12px;
    margin:7px 0;
    background:#252525;
    color:white;
    border:1px solid #444;
    border-radius:7px;
    max-width:100%;
}
.card {
    background:#1d1d1d;
    padding:17px;
    border-radius:12px;
    margin:15px 0;
    max-width:800px;
}
video {
    width:100%;
    max-height:450px;
    background:black;
    border-radius:8px;
}
small { color:#aaa; }
.muted { color:#aaa; }
input[type=file] { width:100%; }
.comment { background:#292929; padding:10px; border-radius:7px; margin:7px 0; }
"""

HEADER = """
<header>
<a class="logo" href="/">5TVE</a>
<nav>
<a href="/">Ana Sayfa</a>
{% if user %}
<a href="/profil">Profilim</a>
<a href="/cikis">Çıkış</a>
{% else %}
<a href="/giris">Giriş</a>
<a href="/kayit">Kayıt Ol</a>
{% endif %}
</nav>
</header>
"""

HOME = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>5TVE</title>
<style>{{ style }}</style>
</head>
<body>
{{ header|safe }}
<main>
<h1>Videoları keşfet</h1>

<form method="get" action="/">
<input name="q" placeholder="Video ara..." value="{{ q }}">
<button>Ara</button>
</form>

{% if user %}
<div class="card">
<h2>Video yükle</h2>
<form action="/yukle" method="post" enctype="multipart/form-data">
<input name="title" placeholder="Video başlığı" maxlength="100" required><br>
<input type="file" name="video" accept="video/mp4,video/webm,video/quicktime" required><br>
<small>En fazla 200 MB. MP4, WEBM veya MOV.</small><br><br>
<button type="submit">Videoyu yayınla</button>
</form>
</div>
{% endif %}

{% for v in videos %}
<div class="card">
<h2>{{ v.title }}</h2>
<small>
<a href="/kanal/{{ v.owner }}">{{ v.owner }}</a>
· {{ v.created_at }}
</small>
<br><br>
<video controls preload="metadata">
<source src="/video/{{ v.filename }}">
Tarayıcın video oynatmayı desteklemiyor.
</video>
<p>❤️ {{ v.like_count }} beğeni</p>

{% if user %}
<form action="/begeni/{{ v.id }}" method="post">
<button type="submit">
{% if v.liked %}❤️ Beğeniyi geri al{% else %}🤍 Beğen{% endif %}
</button>
</form>
<form action="/yorum/{{ v.id }}" method="post">
<input name="comment" placeholder="Yorum yaz..." maxlength="500" required>
<button>Yorum gönder</button>
</form>
{% else %}
<p><a href="/giris">Beğenmek ve yorum yapmak için giriş yap.</a></p>
{% endif %}

{% for c in v.comments %}
<div class="comment">
<b><a href="/kanal/{{ c.username }}">{{ c.username }}</a></b>
<p>{{ c.content }}</p>
</div>
{% endfor %}
</div>
{% else %}
<p>Henüz video bulunamadı.</p>
{% endfor %}
</main>
</body>
</html>
"""

AUTH = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>5TVE - {{ title }}</title>
<style>
{{ style }}
.auth { max-width:400px; margin:60px auto; text-align:center; }
.auth input { width:100%; }
</style>
</head>
<body>
{{ header|safe }}
<div class="card auth">
<h1>{{ title }}</h1>
{% if error %}<p>{{ error }}</p>{% endif %}
<form method="post">
<input name="username" placeholder="Kullanıcı adı" minlength="3" maxlength="24" required>
<input name="password" type="password" placeholder="Şifre" minlength="6" required>
<button type="submit">{{ title }}</button>
</form>
<p><a href="/">Ana sayfaya dön</a></p>
</div>
</body>
</html>
"""

PROFILE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ channel }} - 5TVE</title>
<style>{{ style }}</style>
</head>
<body>
{{ header|safe }}
<main>
<div class="card">
<h1>👤 {{ channel }}</h1>
<h3>Kanal</h3>
<p>{{ videos|length }} video</p>
</div>
<h2>Yüklenen videolar</h2>
{% for v in videos %}
<div class="card">
<h3>{{ v.title }}</h3>
<small>{{ v.created_at }}</small>
<br><br>
<video controls preload="metadata">
<source src="/video/{{ v.filename }}">
</video>
<p>❤️ {{ v.like_count }} beğeni</p>
</div>
{% else %}
<p>Bu kanalda henüz video yok.</p>
{% endfor %}
</main>
</body>
</html>
"""


def get_video_data(user=None, search=""):
    con = db()
    if search:
        rows = con.execute("""
            SELECT * FROM videos
            WHERE title LIKE ?
            ORDER BY id DESC
        """, ("%" + search + "%",)).fetchall()
    else:
        rows = con.execute("""
            SELECT * FROM videos ORDER BY id DESC
        """).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["like_count"] = con.execute(
            "SELECT COUNT(*) FROM likes WHERE video_id=?",
            (row["id"],)
        ).fetchone()[0]

        item["liked"] = False
        if user:
            item["liked"] = con.execute(
                "SELECT 1 FROM likes WHERE video_id=? AND username=?",
                (row["id"], user)
            ).fetchone() is not None

        item["comments"] = con.execute("""
            SELECT username, content FROM comments
            WHERE video_id=? ORDER BY id DESC
        """, (row["id"],)).fetchall()

        result.append(item)

    con.close()
    return result


@app.route("/")
def home():
    user = session.get("user")
    q = request.args.get("q", "").strip()
    videos = get_video_data(user, q)

    return render_template_string(
        HOME, style=STYLE, header=HEADER,
        user=user, videos=videos, q=q
    )


@app.route("/kayit", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username.replace("_", "").isalnum():
            error = "Kullanıcı adında sadece harf, rakam ve alt çizgi kullan."
        elif len(username) < 3 or len(username) > 24:
            error = "Kullanıcı adı 3-24 karakter olmalı."
        elif len(password) < 6:
            error = "Şifre en az 6 karakter olmalı."
        else:
            con = db()
            try:
                con.execute(
                    "INSERT INTO users(username,password) VALUES (?,?)",
                    (username, generate_password_hash(password))
                )
                con.commit()
                session["user"] = username
                con.close()
                return redirect("/")
            except sqlite3.IntegrityError:
                error = "Bu kullanıcı adı zaten alınmış."
            finally:
                con.close()

    return render_template_string(
        AUTH, title="Kayıt Ol", error=error,
        style=STYLE, header=HEADER, user=session.get("user")
    )


@app.route("/giris", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        con = db()
        account = con.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        con.close()

        if account and check_password_hash(account["password"], password):
            session.clear()
            session["user"] = username
            return redirect("/")
        error = "Kullanıcı adı veya şifre yanlış."

    return render_template_string(
        AUTH, title="Giriş Yap", error=error,
        style=STYLE, header=HEADER, user=session.get("user")
    )


@app.route("/cikis")
def logout():
    session.clear()
    return redirect("/")


@app.route("/profil")
@login_required
def my_profile():
    return redirect(url_for("channel", username=session["user"]))


@app.route("/kanal/<username>")
def channel(username):
    con = db()
    account = con.execute(
        "SELECT username FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if not account:
        con.close()
        abort(404)

    rows = con.execute("""
        SELECT * FROM videos WHERE owner=? ORDER BY id DESC
    """, (username,)).fetchall()

    videos = []
    for row in rows:
        item = dict(row)
        item["like_count"] = con.execute(
            "SELECT COUNT(*) FROM likes WHERE video_id=?",
            (row["id"],)
        ).fetchone()[0]
        videos.append(item)

    con.close()

    return render_template_string(
        PROFILE, style=STYLE, header=HEADER,
        user=session.get("user"), channel=username,
        videos=videos
    )


@app.route("/yukle", methods=["POST"])
@login_required
def upload():
    title = request.form.get("title", "").strip()
    file = request.files.get("video")

    if not title or not file or not file.filename:
        flash("Başlık ve video gerekli.")
        return redirect("/")

    if not allowed_file(file.filename):
        return "Desteklenmeyen video formatı. MP4, WEBM veya MOV kullan.", 400

    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    unique_name = uuid.uuid4().hex + "." + extension

    file.save(os.path.join(UPLOAD_FOLDER, unique_name))

    con = db()
    con.execute(
        "INSERT INTO videos(title,filename,owner) VALUES (?,?,?)",
        (title, unique_name, session["user"])
    )
    con.commit()
    con.close()

    return redirect("/")


@app.route("/video/<filename>")
def serve_video(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/begeni/<int:video_id>", methods=["POST"])
@login_required
def like(video_id):
    con = db()
    exists = con.execute(
        "SELECT id FROM videos WHERE id=?",
        (video_id,)
    ).fetchone()

    if not exists:
        con.close()
        abort(404)

    current = con.execute(
        "SELECT id FROM likes WHERE video_id=? AND username=?",
        (video_id, session["user"])
    ).fetchone()

    if current:
        con.execute(
            "DELETE FROM likes WHERE video_id=? AND username=?",
            (video_id, session["user"])
        )
    else:
        con.execute(
            "INSERT INTO likes(video_id,username) VALUES (?,?)",
            (video_id, session["user"])
        )

    con.commit()
    con.close()
    return redirect("/")


@app.route("/yorum/<int:video_id>", methods=["POST"])
@login_required
def comment(video_id):
    content = request.form.get("comment", "").strip()

    if content:
        con = db()
        exists = con.execute(
            "SELECT id FROM videos WHERE id=?",
            (video_id,)
        ).fetchone()

        if exists:
            con.execute("""
                INSERT INTO comments(video_id,username,content)
                VALUES (?,?,?)
            """, (video_id, session["user"], content[:500]))
            con.commit()

        con.close()

    return redirect("/")


@app.errorhandler(413)
def too_large(error):
    return "Video 200 MB sınırını aşıyor.", 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
