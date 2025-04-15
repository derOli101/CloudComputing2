# Flask & Co. Imports
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import os
from openai import OpenAI
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# Flask App initialisieren
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Für Sessions (sollte in Produktion sicherer sein)

# PostgreSQL-Datenbankkonfiguration (z. B. über Terraform bereitgestellt)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# OpenAI GPT-Client initialisieren
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Datenbankmodell für die Körperzusammensetzung
class BodyComposition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Nutzername
    weight = db.Column(db.Float, nullable=False)      # Gewicht in kg
    height = db.Column(db.Float)                      # Größe in cm
    fat_percentage = db.Column(db.Float, nullable=False)  # Körperfettanteil in %
    date = db.Column(db.String(10), default=func.now())   # Datum des Eintrags (als String)

# In-Memory-Cache für Nutzer (Sessionspeicher, z. B. Größe)
users = {}

# Hilfsfunktion zum Laden des Hauptkontextes für das Template
def get_main_context():
    user = session["user"]
    today = datetime.today().strftime('%Y-%m-%d')

    # Alle Einträge des aktuellen Nutzers laden
    entries = BodyComposition.query.filter_by(name=user).all()

    # Letzte bekannte Größe speichern
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

# Login-Seite: Benutzername eingeben
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

# Hauptseite nach Login – hier werden Daten eingegeben und angezeigt
@app.route("/main", methods=["GET", "POST"])
def main():
    if "user" not in session:
        return redirect(url_for("login"))

    context = get_main_context()

    if request.method == "POST":
        # Formulareingaben lesen
        weight = request.form.get("weight")
        fat_percentage = request.form.get("fat_percentage")
        date = request.form.get("date") or context["today"]
        new_height = request.form.get("height")

        # Neue Größe speichern (auch im Cache)
        if new_height:
            users[context["user"]]["height"] = new_height
            context["height"] = new_height

        # Wenn Daten vollständig: neuen Eintrag speichern
        if weight and fat_percentage:
            entry = BodyComposition(
                name=context["user"],
                weight=float(weight),
                fat_percentage=float(fat_percentage),
                height=float(context["height"]) if context["height"] else None,
                date=date
            )
            db.session.add(entry)
            db.session.commit()

    # Kontext nach Speicherung neu laden
    context = get_main_context()
    return render_template("main.html", **context)

# Route für KI-generierten Fitness-Tipp basierend auf den bisherigen Daten
@app.route("/fitness-tip", methods=["POST"])
def fitness_tip():
    if "user" not in session:
        return redirect(url_for("login"))

    context = get_main_context()
    user = context["user"]

    user_history = context["body_compositions"]

    # Wenn noch keine Daten vorhanden sind: Hinweis anzeigen
    if not user_history:
        context["fitness_tip"] = "Es sind noch keine Körperdaten vorhanden. Bitte zuerst Gewicht und Fettanteil eingeben."
        return render_template("main.html", **context)

    # Verlauf als Text zusammenfassen
    history_text = "\n".join(
        f"- {entry.date}: {entry.weight} kg, {entry.fat_percentage}% Körperfett, Größe {entry.height or 'n/a'} cm"
        for entry in user_history
    )

    # Prompt an GPT vorbereiten
    prompt = (
        f"Hier sind die Körperdaten eines Nutzers:\n\n"
        f"{history_text}\n\n"
        f"Gib einen kurzen Fitness-Tipp zur Reduktion von Körperfett. "
        f"Berücksichtige den Verlauf und motiviere den Nutzer. "
        f"Lasse in deiner Antwort Begrüßungen weg, es soll die Ausgabe einer Web-App sein."
    )

    try:
        # OpenAI Chat Completion aufrufen
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

    # Tipp im Kontext anzeigen
    context["fitness_tip"] = tip
    return render_template("main.html", **context)

# Logout: Session löschen und zurück zur Login-Seite
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# App-Start (nur bei direktem Aufruf)
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Datenbanktabellen anlegen (nur beim ersten Start notwendig)
    app.run(debug=True, host="0.0.0.0", port=5000)
