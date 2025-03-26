from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime


def get_main_context():
    user = session["user"]
    today = datetime.today().strftime('%Y-%m-%d')

    if user not in users:
        users[user] = {"height": None}

    return {
        "user": user,
        "today": today,
        "height": users[user]["height"],
        "body_compositions": body_compositions
    }

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Für Session-Handling

# In-Memory "DB"
users = {}
body_compositions = []

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
            body_compositions.append({
                "name": context["user"],
                "weight": weight,
                "height": context["height"],
                "fat_percentage": fat_percentage,
                "date": date
            })

    return render_template("main.html", **context)


@app.route("/fitness-tip", methods=["POST"])
def fitness_tip():
    if "user" not in session:
        return redirect(url_for("login"))

    context = get_main_context()
    context["fitness_tip"] = "Du solltest Cardio Training priorisieren, um deinen Körperfettanteil zu reduzieren."

    return render_template("main.html", **context)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
