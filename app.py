import os
from flask.templating import render_template_string
import requests
import json
from flask import Flask, session, g, request, redirect, url_for, render_template, flash
from flask_session import Session
from sqlalchemy.sql.elements import Null
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from sqlalchemy import create_engine
from tempfile import mkdtemp
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime, date

UPLOAD_FOLDER = "./static/img/"
ALLOWED_EXTENSIONS = {'.jpg', '.png', '.psd','.svg'}

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
Session(app)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

cat = db.execute("SELECT type FROM types").fetchall()
tags = db.execute("SELECT tag FROM tags ORDER BY RANDOM() LIMIT 5").fetchall()

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
#@login_required
def main():

    try:
        session["user_id"]
        usuario = db.execute("SELECT username,age FROM users WHERE user_id = :user_id", {"user_id":session["user_id"]}).fetchall()
        
        nombre_usuario = usuario[0]["username"]
        age= usuario[0]["age"]
        
        if age < 18:
            info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL").fetchall()
            print(info)
        else:
            info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id").fetchall()
        
        return render_template("index.html", info = info, cat = cat, username1 = nombre_usuario, tags = tags)
    except:
        info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL").fetchall()
        print(tags)
        return render_template("index.html", info = info, cat = cat, tags = tags)

@app.route("/register",  methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        name = request.form.get("name")
        confirm = request.form.get("confirm")
        birthday = request.form.get("birthday")

        # Reguero para nada más dividir el string de la fecha porque no quise crear más condiciones
        birth = birthday.split("-")
        anio = int(birth[0])
        month = int(birth[1])
        day = int(birth[2])

        # Ahora sí calcula la edad :)
        age = calculateAge(date(anio, month, day))

        usernamedb = db.execute("SELECT username FROM users WHERE username = :username", {"username": request.form.get("username")}).fetchall()
        
        if not username or not password or not name or not confirm:
            flash('Debe rellenar todos los campos')
            return render_template("register.html")
    
        if confirm != password:
            flash('Las contraseñas no coinciden')
            return render_template("register.html")

        if len(usernamedb) != 0:
            flash('El nombre de usuario ya está en uso')
            return render_template("register.html")
        
        if len(usernamedb) == 0 and password == confirm:
            datos = db.execute("INSERT INTO users (username, password, name, age) VALUES (:username,:password,:name, :age) RETURNING user_id", { "username": username, "password" : generate_password_hash(password), "name": name, "age": age}).fetchall()
            db.commit()

            session["user_id"] = datos[0]["user_id"]

            url_icon = "https://icons-for-free.com/iconfiles/png/512/avatar+human+people+profile+user+icon-1320168139431219590.png"
            db.execute("INSERT INTO profiles (user_id, icon) VALUES (:user_id, :icon)", {"user_id": session["user_id"], "icon": url_icon})
            db.commit()
        return redirect("/")
    else:
        return render_template("register.html", cat=cat, tags = tags)

# https://www.geeksforgeeks.org/python-program-to-calculate-age-in-year/
def calculateAge(born):
    today = date.today()
    try:
        birthday = born.replace(year = today.year)
 
    # raised when birth date is February 29
    # and the current year is not a leap year
    except ValueError:
        birthday = born.replace(year = today.year,
                  month = born.month + 1, day = 1)
 
    if birthday > today:
        return today.year - born.year - 1
    else:
        return today.year - born.year
     

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchall()
        print(user)
        if not username or not password:
            flash('Debe rellenar todos los campos')
            return render_template("login.html")
        if len(user) == 0:
            Error = 'Invalid credentials'
            flash('Nombre de usuario o contraseña inválidos')
            return render_template("login.html")
        if not check_password_hash(user[0]["password"], password):
            Error = 'Invalid credentials'
            flash('Nombre de usuario o contraseña inválidos')
            return render_template("login.html")

        session["user_id"] = user[0]["user_id"]

        user_id = session["user_id"]
        return redirect("/")
    else:
        return render_template("login.html", cat = cat, tags = tags)


@app.route("/upload", methods=["GET", "POST"])
@login_required
def crearpost():
    if request.method == "POST":

        if "archivo" not in request.files:
            return render_template("subir_img.html")
        
        archivo = request.files['archivo']

        if archivo.filename == "":
            return render_template("subir_img.html")

        if archivo:
            nombreArchivo = archivo.filename
            archivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))
            now = datetime.now()
            desc = request.form.get("texto")
            tipo = request.form.get("type")
            rate = request.form.get("rate")

            # Obtiene los tags desde el input
            tag_1 = request.form.get("tags")

            # Separa los tags al encontrar un espacio
            tags = tag_1.split()

            # dd/mm/YY H:M:S
            fecha = now.strftime("%d %B, %Y")

            x = db.execute("SELECT type_id FROM types WHERE type = :type", {"type": tipo}).fetchall() 
            num_type = x[0]["type_id"]

            #(f"INSERT INTO usuario (username,password,name,lastname,email) VALUES ('{username}','{password}','{nombre}','{apellido}','{email}''')")
            save = db.execute("INSERT INTO posts (user_id, description, photo, fecha, type, rate) VALUES (:user_id, :texto, :urlimg, :fecha, :num_type, :rate) RETURNING post_id",{ "user_id": session["user_id"], "texto" : desc, "urlimg" : (os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))[1:len(os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))], "fecha": fecha, "num_type": num_type, "rate": rate }).fetchall()
            db.commit()

            postid = save[0]["post_id"]
            for x in tags:
                db.execute("INSERT INTO tags (user_id, post_id, tag) VALUES (:user_id, :post_id, :tag) ",{ "user_id":session["user_id"],"post_id": postid, "tag" : x })
                db.commit()
            return redirect("/")
        else:
            return render_template("subir_img.html", cat=cat)
    else:
        opc = db.execute("SELECT type FROM types").fetchall()
        return render_template("subir_img.html", coincidencias = opc, cat = cat)

@app.route("/topics/<type>")
def topics(type):
    topic = db.execute("SELECT posts.post_id, posts.user_id, photo, username FROM posts INNER JOIN types ON posts.type = types.type_id INNER JOIN users ON posts.user_id = users.user_id WHERE types.type = :type", {"type":type}).fetchall()
    return render_template("categorias.html", topic = topic, cat = cat, tags = tags, type = type)

@app.route("/tag/<tag>")
def tag(tag):
    tags2 = db.execute("SELECT posts.user_id, photo, posts.post_id, tag FROM posts INNER JOIN tags ON tags.post_id = posts.post_id WHERE tag = :tag", {"tag":tag}).fetchall()
    return render_template("tags.html", tag_html = tags2, cat = cat, tags = tags)

@app.route("/search", methods=["GET", "POST"])
#@login_required
def buscar():
    if request.method == "POST":
        busq = request.form.get("search")
        a = '%'+busq+'%'

        print(a)
        by_tag = db.execute("SELECT posts.user_id, photo, posts.post_id, tag FROM posts INNER JOIN tags ON tags.post_id = posts.post_id WHERE LOWER(tag) LIKE LOWER(:busq)", {"busq":a}).fetchall()
        
        # Busqueda por descripción
        descripcion = db.execute("SELECT posts.user_id, photo, posts.post_id, tag FROM posts INNER JOIN tags ON tags.post_id = posts.post_id WHERE LOWER(description) LIKE LOWER(:busq)", {"busq":a}).fetchall()
        
        usuarios = db.execute("SELECT username, name FROM users WHERE LOWER(username) LIKE LOWER(:busq)", {"busq": a}).fetchall()

        if len(by_tag) == 0:
            tag_disp = False
        else:
            tag_disp = True
        
        
        if len(descripcion) == 0:
            desc_disp = False
        else:
            desc_disp = True
        
        if len(usuarios) == 0:
            user_disp = False
        else:
            user_disp = True
        
        print(by_tag)
        print(descripcion)
        print(usuarios)
        print(user_disp)
        return render_template("resultados.html", por_tag = by_tag, desc= descripcion, cat=cat, tags = tags, users = usuarios, tag = tag_disp, user = user_disp)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings(username):
    if request.method == "POST":
        description = request.form.get("texto")
        if "archivo" not in request.files:
            db.execute("UPDATE profiles SET description = :description WHERE user_id = :user_id",{"user_id": session["user_id"]})
            db.commit()
        
        archivo = request.files['archivo']
        
        if archivo.filename == "":
            return render_template("subir_img.html")

        if archivo:
            nombreArchivo = archivo.filename
            archivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))

            url_img = (os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))[1:len(os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))]
            
            print(url_img)

            db.execute("UPDATE profiles SET icon = :icon, description = :description WHERE user_id = :user_id ", {"icon": url_img, "description": description, "user_id": session["user_id"]})
            db.commit()

        return redirect("/profile/"+username)
    xd = db.execute("SELECT description FROM profiles WHERE user_id = :user_id",{"user_id": session["user_id"]}).fetchall()
    perfil_desc = xd[0]["description"]

    return render_template("settings.html", desc = perfil_desc)

@app.route("/profile/<username>")
def perfil(username):

    xd = db.execute("SELECT user_id FROM users WHERE username = :username", {"username": username}).fetchall()
    user_id = xd[0]["user_id"]
    info = db.execute("SELECT username, name, profiles.user_id, description, icon FROM users INNER JOIN profiles ON users.user_id = profiles.user_id WHERE profiles.user_id = :user_id", {"user_id": user_id}).fetchall()
    user= info[0]["user_id"]
    posts = db.execute("SELECT * FROM posts WHERE user_id = :user_id", {"user_id": user}).fetchall()

    print(posts)
    try:
        desc = info[0]["description"] 
    except:

        desc = "Este usuario no tiene una descripción"

    print(info)
    return render_template("profile.html", info = info, desc= desc, cat=cat, tags = tags, username = username)

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")