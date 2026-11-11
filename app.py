
import os
from flask import Flask, request, redirect, url_for, session, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "5tve-secret-key-change-later")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

users = {}
videos = []
likes = set()
comments = []

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>5TVE</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0f0f0f;color:white;font-family:Arial}
header{background:#181818;padding:18px 5%;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:28px;font-weight:bold;color:#ff3030}
a{color:white;text-decoration:none}
button,.btn{background:#ff3030;color:white;border:0;padding:10px 16px;border-radius:7px;cursor:pointer}
main{padding:25px 5%}
input{padding:11px;margin:6px 0;background:#252525;color:white;border:1px solid #444;border-radius:6px}
.card{background:#1d1d1d;padding:15px;border-radius:12px;margin:12px 0;max-width:700px}
video{width:100%;max-height:400px;background:black}
small{color:#aaa}
</style>
</head>
<body>
<header>
<a class="logo" href="/">5TVE</a>
<div>
{% if user %}
<span>{{user}}</span> &nbsp;
<a href="/cikis">Çıkış</a>
{% else %}
<a href="/giris">Giriş</a> &nbsp;
<a href="/kayit">Kayıt ol</a>
{% endif %}
</div>
</header>
<main>
<h1>Videoları keşfet</h1>
{% if user %}
<div class="card">
<h3>Video yükle</h3>
<form action="/yukle" method="post" enctype="multipart/form-data">
<input name="title" placeholder="Video başlığı" required><br>
<input type="file" name="video" accept="video/*" required><br>
<button>Yayınla</button>
</form>
</div>
{% endif %}
{% for v in videos %}
<div class="card">
<h3>{{v.title}}</h3>
<small>{{v.owner}} tarafından yüklendi</small>
<video controls preload="metadata">
<source src="/video/{{v.filename}}">
</video>
{% if user %}
<form action="/begeni/{{v.id}}" method="post">
<button>❤️ Beğen</button>
</form>
<form action="/yorum/{{v.id}}" method="post">
<input name="comment" placeholder="Yorum yaz..." required>
<button>Gönder</button>
</form>
{% endif %}
{% for c in comments %}
{% if c.video_id == v.id %}
<p><b>{{c.user}}:</b> {{c.text}}</p>
{% endif %}
{% endfor %}
</div>
{% else %}
<p>Henüz video yüklenmedi.</p>
{% endfor %}
{% if error %}<p>{{error}}</p>{% endif %}
</main>
</body>
</html>
"""

AUTH = """
<!DOCTYPE html><html lang="tr"><meta charset="UTF-8">
<title>5TVE</title>
<style>body{background:#111;color:white;font-family:Arial;text-align:center;padding:50px}
input{padding:12px;margin:8px;background:#222;color:white;border:1px solid #555}
button{padding:12px;background:#f33;color:white;border:0;cursor:pointer}</style>
<h1>5TVE</h1><h2>{{title}}</h2>
<form method="post">
<input name="username" placeholder="Kullanıcı adı" required><br>
<input name="password" type="password" placeholder="Şifre" required><br>
<button>{{title}}</button>
</form><p>{{error}}</p><a href="/">Ana sayfa</a></html>
"""

@app.route("/")
def home():
    return render_template_string(HTML, user=session.get("user"),
                                  videos=videos, comments=comments, error=None)

@app.route("/kayit", methods=["GET","POST"])
def kayit():
    error = ""
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        if len(u) < 3 or len(p) < 6:
            error = "Kullanıcı adı en az 3, şifre en az 6 karakter olmalı."
        elif u in users:
            error = "Bu kullanıcı adı zaten kullanılıyor."
        else:
            users[u] = generate_password_hash(p)
            session["user"] = u
            return redirect("/")
    return render_template_string(AUTH, title="Kayıt ol", error=error)

@app.route("/giris", methods=["GET","POST"])
def giris():
    error = ""
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        if u in users and check_password_hash(users[u], p):
            session["user"] = u
            return redirect("/")
        error = "Kullanıcı adı veya şifre hatalı."
    return render_template_string(AUTH, title="Giriş yap", error=error)

@app.route("/cikis")
def cikis():
    session.clear()
    return redirect("/")

@app.route("/yukle", methods=["POST"])
def yukle():
    if "user" not in session:
        return redirect("/giris")
    f = request.files.get("video")
    title = request.form.get("title", "").strip()
    if not f or not f.filename or not title:
        return redirect("/")
    if not f.mimetype.startswith("video/"):
        return "Sadece video yükleyebilirsin.", 400
    filename = secure_filename(f.filename)
    filename = str(len(videos)+1) + "_" + filename
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    videos.append({"id":len(videos)+1, "title":title,
                   "owner":session["user"], "filename":filename})
    return redirect("/")

@app.route("/video/<filename>")
def video(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/begeni/<int:vid>", methods=["POST"])
def begeni(vid):
    if "user" not in session:
        return redirect("/giris")
    key = (vid, session["user"])
    if key in likes:
        likes.remove(key)
    else:
        likes.add(key)
    return redirect("/")

@app.route("/yorum/<int:vid>", methods=["POST"])
def yorum(vid):
    if "user" not in session:
        return redirect("/giris")
    t = request.form.get("comment", "").strip()
    if t and any(v["id"] == vid for v in videos):
        comments.append({"video_id":vid, "user":session["user"], "text":t})
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
