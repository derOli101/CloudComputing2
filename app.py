from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import os
from openai import OpenAI
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "supersecretkey"

# PostgreSQL DB von Terraform
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# OpenAI GPT
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# DB-Modell
class BodyComposition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    height = db.Column(db.Float)
    fat_percentage = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(10), default=func.now())

# In-Memory-Daten (für Sessions – optional)
users = {}

def get_main_context():
    user = session["user"]
    today = datetime.today().strftime('%Y-%m-%d')

    # Lade Userdaten aus DB
    entries = BodyComposition.query.filter_by(name=user).all()

    # Höhe merken (letzter bekannter Eintrag)
    if user not in users:
        users[user] = {"height": None}
    if entries:
        users[user]["height"] = entries[-1].height or users[user]["height"]

    return {
        "user": user,
        "today": today,
        "height": users[user]["height"],
        "body_compositions": entries
    }

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            session["user"] = name
            if name not in users:
                users[name] = {"height": None}
            return redirect(url_for("main"))
    return render_template("login.html")

@app.route("/main", methods=["GET", "POST"])
def main():
    if "user" not in session:
        return redirect(url_for("login"))

    context = get_main_context()

    if request.method == "POST":
        weight = request.form.get("weight")
        fat_percentage = request.form.get("fat_percentage")
        date = request.form.get("date") or context["today"]
        new_height = request.form.get("height")

        if new_height:
            users[context["user"]]["height"] = new_height
            context["height"] = new_height

        if weight and fat_percentage:
            # In DB speichern
            entry = BodyComposition(
                name=context["user"],
                weight=float(weight),
                fat_percentage=float(fat_percentage),
                height=float(context["height"]) if context["height"] else None,
                date=date
            )
            db.session.add(entry)
            db.session.commit()

    # Kontext neu laden (nach speichern)
    context = get_main_context()
    return render_template("main.html", **context)

@app.route("/fitness-tip", methods=["POST"])
def fitness_tip():
    if "user" not in session:
        return redirect(url_for("login"))

    context = get_main_context()
    user = context["user"]

    user_history = context["body_compositions"]

    if not user_history:
        context["fitness_tip"] = "Es sind noch keine Körperdaten vorhanden. Bitte zuerst Gewicht und Fettanteil eingeben."
        return render_template("main.html", **context)

    history_text = "\n".join(
        f"- {entry.date}: {entry.weight} kg, {entry.fat_percentage}% Körperfett, Größe {entry.height or 'n/a'} cm"
        for entry in user_history
    )

    prompt = (
        f"Hier sind die Körperdaten eines Nutzers:\n\n"
        f"{history_text}\n\n"
        f"Gib einen kurzen Fitness-Tipp zur Reduktion von Körperfett. "
        f"Berücksichtige den Verlauf und motiviere den Nutzer. "
        f"Lasse in deiner Antwort Begrüßungen weg, es soll die Ausgabe einer Web-App sein."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du bist ein motivierender Fitness-Coach."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.8
        )
        tip = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT-Fehler: {e}")
        tip = "Tipp konnte nicht geladen werden. Bitte versuche es später erneut."

    context["fitness_tip"] = tip
    return render_template("main.html", **context)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Nur beim ersten Start nötig
    app.run(debug=True, host="0.0.0.0", port=80)
