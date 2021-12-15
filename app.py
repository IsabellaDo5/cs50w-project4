import os
from flask.templating import render_template_string
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
ALLOWED_EXTENSIONS = {'.jpg','.jpeg', '.png', '.psd','.svg'}

#REPOSITORIO
REPOS_FOLDER = "./static/repositorio/"
app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#REPOSITORIO
app.config['REPOS_FOLDER'] = REPOS_FOLDER
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

# Página de inicio
@app.route("/")
def main():

    try:
        a = session["user_id"]
        #usuario = db.execute("SELECT username, name, icon FROM users INNER JOIN profiles ON profiles.user_id = users.user_id WHERE users.user_id = :user_id", {"user_id":a }).fetchall()
        
        usuario = db.execute("SELECT age FROM users WHERE user_id = :user_id", {"user_id": session["user_id"]}).fetchall()
        age = usuario[0]["age"]
        
        if age < 18:
            info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL ORDER BY post_id DESC").fetchall()

            # Más popular
            most_pop = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL ORDER BY likes DESC LIMIT 5").fetchall()
        else:
            # Inicio
            info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id ORDER BY post_id DESC").fetchall()

            # Más popular
            info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id ORDER BY likes DESC LIMIT 5").fetchall()

        info_user= db.execute("SELECT username, name, icon FROM users INNER JOIN profiles ON profiles.user_id = users.user_id WHERE users.user_id = :user_id", {"user_id":session["user_id"] }).fetchall()
        
        
        print(info_user)

        return render_template("index.html", info = info, cat = cat, tags = tags, info_usuario = usuario, popular = most_pop)
    except:
        info = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL ORDER BY post_id DESC").fetchall()

        # Busca los posts con más likes 
        most_pop = db.execute("SELECT posts.user_id, post_id, username, photo, fecha FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE posts.rate IS NULL ORDER BY likes DESC LIMIT 5").fetchall()

        '''db.execute("UPDATE users SET admin = :admin WHERE user_id = :user_id", {"admin": 1, "user_id": 42})
        db.commit()'''
        return render_template("index.html", info = info, cat = cat, tags = tags, popular = most_pop)

# Registro
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
     
# Pagina de inicio de sesión
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

# Sube los posts
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
            save = db.execute("INSERT INTO posts (user_id, description, photo, fecha, type, rate, likes) VALUES (:user_id, :texto, :urlimg, :fecha, :num_type, :rate, :likes) RETURNING post_id",{ "user_id": session["user_id"], "texto" : desc, "urlimg" : (os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))[1:len(os.path.join(app.config["UPLOAD_FOLDER"], nombreArchivo))], "fecha": fecha, "num_type": num_type, "rate": rate, "likes":0 }).fetchall()
            db.commit()

            postid = save[0]["post_id"]
            for x in tags:
                db.execute("INSERT INTO tags (user_id, post_id, tag) VALUES (:user_id, :post_id, :tag) ",{ "user_id":session["user_id"],"post_id": postid, "tag" : x })
                db.commit()
            return redirect("/")
        else:
            return render_template("subir_img.html", cat=cat,)
    else:
        opc = db.execute("SELECT type FROM types").fetchall()
        tags = db.execute("SELECT tag FROM tags ORDER BY RANDOM() LIMIT 5").fetchall()
        return render_template("subir_img.html", coincidencias = opc, cat = cat, tags = tags)

# Muestra los posts que coinciden con la categoría seleccionada
@app.route("/topics/<type>")
def topics(type):
    topic = db.execute("SELECT posts.post_id, posts.user_id, photo, username FROM posts INNER JOIN types ON posts.type = types.type_id INNER JOIN users ON posts.user_id = users.user_id WHERE types.type = :type", {"type":type}).fetchall()
    return render_template("categorias.html", topic = topic, cat = cat, tags = tags, type = type)

# muestra todos los posts con los tags que coinciden
@app.route("/tag/<tag>")
def tag(tag):
    tags2 = db.execute("SELECT posts.user_id, photo, posts.post_id, tag FROM posts INNER JOIN tags ON tags.post_id = posts.post_id WHERE tag = :tag", {"tag":tag}).fetchall()
    
    titulo = tags2[0]["tag"]
    return render_template("tags.html", tag_html = tags2, cat = cat, tags = tags, titulo = titulo)

# búsqueda
@app.route("/search", methods=["GET", "POST"])
def buscar():
    if request.method == "POST":
        busq = request.form.get("search")
        a = '%'+busq+'%'

        print(a)
        by_tag = db.execute("SELECT posts.user_id, photo, posts.post_id, tag FROM posts INNER JOIN tags ON tags.post_id = posts.post_id WHERE LOWER(tag) LIKE LOWER(:busq)", {"busq":a}).fetchall()
        
        # Busqueda por descripción
        descripcion = db.execute("SELECT user_id, photo, post_id FROM posts WHERE LOWER(description) LIKE LOWER(:busq)", {"busq":a}).fetchall()
        
        usuarios = db.execute("SELECT username, name, icon FROM users INNER JOIN profiles ON profiles.user_id = users.user_id WHERE LOWER(username) LIKE LOWER(:busq)", {"busq": a}).fetchall()

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
        return render_template("resultados.html", por_tag = by_tag, desc= descripcion, cat=cat, tags = tags, busq = busq, users = usuarios, tag = tag_disp, user = user_disp)

# Muestra la información de un post
@app.route("/post/<post_id>")
def verpost(post_id):

    post = db.execute("SELECT post_id, posts.user_id, photo, description, username, name, likes FROM posts INNER JOIN users ON posts.user_id = users.user_id WHERE post_id = :post_id", {"post_id": post_id}).fetchall()
    tags_p = db.execute("SELECT tag FROM tags WHERE post_id =:post_id", {"post_id": post_id}).fetchall()
    reviews = db.execute("SELECT review_id, comment, date, username, reviews.user_id FROM reviews INNER JOIN users ON reviews.user_id = users.user_id WHERE post_id = :post_id ORDER BY reviews.review_id DESC", {"post_id": post_id}).fetchall()
    
    print(reviews)

    propietario = False

    # Busca si el id del post existe, sino manda un mensaje de error
    try:
        user_id = post[0]["user_id"]
        likes = post[0]["likes"]
        icon = db.execute("SELECT icon from profiles where user_id = :user_id",{"user_id": user_id}).fetchall()
    except:
        return render_template("no_results.html", tag = tags, cat = cat)

    # Da el permiso para eliminar un post si el usuario es el propietario del mismo o es un admin
    try:
        ad = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id": session["user_id"]}).fetchall()
        if session["user_id"] == post[0]["user_id"] or ad[0]["admin"] == 1:
            propietario = True
    except:
        print("No es el usuario")
    
    # Permite eliminar los comentarios si el usuario es admin o el creador del comentario 
    permiso = False
    try:
        ad = db.execute("SELECT * FROM users WHERE user_id = :user_id", {"user_id": session["user_id"]}).fetchall()
        if ad[0]["admin"] == 1:
            permiso = True
    except:
        print("No tiene permiso")

    # try para que no se rompa la página si el usuario no se ha logeado
    like = False
    try:
       info = db.execute("SELECT * FROM likes WHERE user_id = :user_id AND post_id = :post_id",{"user_id": session["user_id"], "post_id":post_id}).fetchall()

       # Confirma si el usuario ya ha dado like o no a la publicación
       if len(info) != 0 and info[0]["me_gusta"] == 1:
           like = True

       # El 0 significa que el usuario registró anteriormente un like pero luego lo quitó
       # por lo que no se marca el corazón en rojo
       elif info[0]["me_gusta"] == 0:
           like = False

       elif len(info) != 0:
           like = True

    # y un except que no hace mucho más q existir
    except:
        print("xd")
    return render_template("post.html", post = post, icon = icon, tags = tags_p, reviews = reviews, propietario = propietario, cat = cat, like = like, cant_likes = likes, permiso = permiso)

@app.route("/delete_review", methods=["GET", "POST"])
@login_required
def d_review():
    if request.method== "POST":
        borrar = request.form.get("info")
        post = db.execute("SELECT post_id FROM reviews WHERE review_id = :review_id", {"review_id": borrar}).fetchall()

        post_id = str(post[0]["post_id"])
        print(post_id)
        db.execute("DELETE FROM reviews WHERE review_id = :review_id", {"review_id": borrar})
        db.commit()
        return redirect("/post/"+post_id)

# Elimina los posts propios
@app.route("/delete_post/<post_id>", methods=["GET", "POST"])
@login_required
def d_post(post_id):
    db.execute("DELETE FROM tags WHERE post_id = :post_id", {"post_id": post_id})
    db.commit()
    db.execute("DELETE FROM posts WHERE post_id = :post_id", {"post_id": post_id})
    db.commit()
    db.execute("DELETE FROM likes WHERE post_id = :post_id", {"post_id": post_id})
    db.commit()
    return redirect("/")

# Agrega los comentarios a la db
@app.route("/review", methods=["GET", "POST"])
@login_required
def reviews():
    if request.method == "POST":
        comment= request.form.get("comentario")
        post_id = request.form.get("info")

        now = datetime.now()
        fecha = now.strftime("%d %B, %Y")
        print(post_id)
        db.execute("INSERT INTO reviews (user_id, comment, post_id, date) VALUES (:user_id, :review, :post_id, :date)", {"review": comment, "user_id": session["user_id"], "post_id": post_id, "date": fecha})
        db.commit()

        return redirect("/post/"+post_id)

# Configuración
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        info = db.execute("SELECT username FROM users WHERE user_id = :user_id", {"user_id": session["user_id"]}).fetchall()
        username = info[0]["username"]

        # Datos del html
        description = request.form.get("texto")
        archivo = request.files['archivo']
        
        if "archivo" not in request.files or archivo.filename == "":
            db.execute("UPDATE profiles SET description = :description WHERE user_id = :user_id",{"user_id": session["user_id"], "description": description})
            db.commit()

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

    return render_template("settings.html", desc = perfil_desc, tags = tags, cat = cat)

# Muestra el perfil del usuario
@app.route("/profile/<username>")
def perfil(username):

    xd = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchall()
    id_user = xd[0]["user_id"]
    info = db.execute("SELECT username, name, profiles.user_id, description, icon FROM users INNER JOIN profiles ON users.user_id = profiles.user_id WHERE profiles.user_id = :user_id", {"user_id": id_user}).fetchall()
    user= info[0]["user_id"]
    posts = db.execute("SELECT * FROM posts WHERE user_id = :user_id ORDER BY post_id DESC", {"user_id": user }).fetchall()

    usuario = False
    print(posts)
    print(id_user)
    try:
        desc = info[0]["description"] 
    except:

        aea = False
    try:
        session["user_id"]
        if id_user == session["user_id"]:
            usuario = True
    except:
        usuario = False

    print(info)
    return render_template("profile.html", info = info, desc= desc, cat=cat, tags = tags, username = username, posts = posts, propietario = usuario)

# repositorio con un espacio de 5 archivos máximos
@app.route("/repo", methods=["GET", "POST"])
@login_required
def repos():
    if request.method == 'POST':
        if "archivo" not in request.files:
            flash("Necesitas agregar un archivo")
            return render_template("repos.html", cat=cat, tags = tags)
            
        archivo = request.files['archivo']
        
        if archivo.filename == "":
            flash("Necesitas agregar un archivo")
            return render_template("repos.html")

        if archivo:
            nombreArchivo = archivo.filename
            archivo.save(os.path.join(app.config["REPOS_FOLDER"], nombreArchivo))

            print(nombreArchivo)
            source = (os.path.join(app.config["REPOS_FOLDER"], nombreArchivo))[1:len(os.path.join(app.config["REPOS_FOLDER"], nombreArchivo))]
            db.execute("INSERT INTO repo (user_id, source, name) VALUES(:user_id, :source, :name)", {"user_id" : session["user_id"], "source": source, "name": nombreArchivo})
            db.commit()

        return redirect("/repo")
    else:

        repo= db.execute("SELECT * FROM repo WHERE user_id = :user_id", {"user_id": session["user_id"]}).fetchall()
        permiso = False
        repo_id = ""

        # try para que no se rompa la página si no tiene nada en el repo
        try:
            repo_id = repo[0]["repo_id"]
            if len(repo)<5:
                permiso = True
        except:
            permiso = True
        return render_template("repos.html", tags = tags, cat = cat, archivos = repo, permiso = permiso, repo_id = repo_id)

# Elimina la ruta de un archivo en la db 
@app.route("/delete_r/<repo_id>", methods=["GET", "POST"])
@login_required
def repo_delete(repo_id):
    if request.method == "POST":
        db.execute("DELETE FROM repo WHERE repo_id = :repo_id", {"repo_id": repo_id})
        db.commit()
        return redirect("/repo")

# agrega el like en la db, mostrandose como un "1"
@app.route("/like", methods=["GET", "POST"])
@login_required
def like():
    if request.method == "POST":
        post_id = request.form.get("info")

        like = db.execute("SELECT me_gusta, like_id FROM likes WHERE user_id = :user_id AND post_id = :post_id", {"user_id": session["user_id"], "post_id": post_id}).fetchall()
        try:
            like_id = like[0]["like_id"]
        except:
            xd = False

        if not like:
            db.execute("INSERT INTO likes (user_id, post_id, me_gusta) VALUES (:user_id, :post_id, :me_gusta)", {"user_id": session["user_id"],"post_id": post_id ,"me_gusta": 1})
            db.commit()
        else:
            db.execute("UPDATE likes SET me_gusta = :me_gusta WHERE post_id = :post_id AND like_id = :like_id", {"me_gusta": 1, "post_id": post_id, "like_id": like_id})
            db.commit()

        num = db.execute("SELECT likes FROM posts WHERE post_id = :post_id", {"post_id": post_id}).fetchall()
        cant = num[0]["likes"]
        db.execute("UPDATE posts SET likes = :likes WHERE post_id = :post_id", {"likes": cant+1, "post_id": post_id})
        db.commit()
        return redirect("/post/"+post_id)

# quita el like de la db cambiando el valor por un 0 y restándole 1 a la tabla posts
@app.route("/dislike", methods=["GET", "POST"])
@login_required
def dislike():
    if request.method == "POST":
        post_id = request.form.get("info")

        like = db.execute("SELECT * FROM likes WHERE user_id = :user_id AND post_id = :post_id", {"user_id": session["user_id"], "post_id": post_id}).fetchall()
        like_id = like[0]["like_id"]

        db.execute("UPDATE likes SET me_gusta = :me_gusta WHERE post_id = :post_id AND like_id = :like_id", {"me_gusta": 0, "post_id": post_id, "like_id": like_id})
        db.commit()

        num = db.execute("SELECT likes FROM posts WHERE post_id = :post_id", {"post_id": post_id}).fetchall()
        cant = num[0]["likes"]
        db.execute("UPDATE posts SET likes = :likes WHERE post_id = :post_id", {"likes": cant-1, "post_id": post_id})
        db.commit()
        return redirect("/post/"+post_id)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")