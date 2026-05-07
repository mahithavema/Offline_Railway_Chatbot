from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import mysql.connector
import re

app = Flask(__name__)
app.secret_key = "secret123"


# -------------------- DB CONNECTION --------------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="$$$$",        # your MySQL password
        database="railway_chatbot"
    )


# -------------------- HOME PAGE --------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------- REGISTER --------------------
@app.route("/register", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        con = get_db()
        cur = con.cursor()

        cur.execute("INSERT INTO users (name,email,phone,password) VALUES (%s,%s,%s,%s)",
                    (name, email, phone, password))
        con.commit()
        con.close()

        return redirect(url_for("login_user"))

    return render_template("register.html")


# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login_user():
    if request.method == "POST":
        identifier = request.form["identifier"]
        password = request.form["password"]

        con = get_db()
        cur = con.cursor(dictionary=True)

        cur.execute("""
            SELECT * FROM users
            WHERE (email=%s OR phone=%s) AND password=%s
        """, (identifier, identifier, password))

        user = cur.fetchone()
        con.close()

        if user:
            session["user"] = user["name"]
            return redirect(url_for("chat_page"))
        else:
            return "Invalid Login"

    return render_template("login.html")


# -------------------- CHAT PAGE --------------------
@app.route("/chat")
def chat_page():
    if "user" not in session:
        return redirect(url_for("login_user"))
    return render_template("chat.html", username=session["user"])


# -------------------- CHATBOT LOGIC --------------------
@app.route("/chatbot", methods=["POST"])
def chatbot():
    msg = request.json["message"].lower().strip()
    username = session["user"]

    con = get_db()
    cur = con.cursor(dictionary=True)

    # -------------------- GREETINGS --------------------
    greetings = ["hi", "hello", "hey", "hii", "hai"]
    if msg in greetings:
        return jsonify({"reply": f"Hello {username}! 👋 Welcome to Railway Assistant. How can I help you today?"})

    # -------------------- TRAIN SEARCH (SRC → DST) --------------------
    if " to " in msg:
        src_text, dst_text = msg.split(" to ")
        src_text = src_text.strip().title()
        dst_text = dst_text.strip().title()

        # Match station by name or station code
        cur.execute("""
            SELECT station_code FROM stations
            WHERE station_name LIKE %s OR station_code=%s
        """, (src_text + "%", src_text.upper()))
        src = cur.fetchone()

        cur.execute("""
            SELECT station_code FROM stations
            WHERE station_name LIKE %s OR station_code=%s
        """, (dst_text + "%", dst_text.upper()))
        dst = cur.fetchone()

        if not src or not dst:
            return jsonify({"reply": "⚠ Station not found."})

        src_code = src["station_code"]
        dst_code = dst["station_code"]

        cur.execute("""
            SELECT * FROM trains 
            WHERE source=%s AND destination=%s
        """, (src_code, dst_code))
        trains = cur.fetchall()

        if not trains:
            return jsonify({"reply": "No trains available for this route."})

        reply = f"🚆 **Trains from {src_text} → {dst_text}:**\n\n"
        for t in trains:
            reply += (
                f"◾ **{t['train_no']} - {t['train_name']}**\n"
                f"⏱ {t['departure_time']} → {t['arrival_time']}\n"
                f"📅 Days: {t['days']}\n\n"
            )

        return jsonify({"reply": reply})

    # -------------------- STATION FACILITIES --------------------
    if "station" in msg:
        station_name = msg.replace("station", "").strip().title()

        cur.execute("""
            SELECT facilities FROM stations 
            WHERE station_name LIKE %s
        """, (station_name + "%",))

        st = cur.fetchone()

        if st:
            return jsonify({"reply": f"🏫 **Facilities at {station_name}:**\n\n{st['facilities']}"})
        else:
            return jsonify({"reply": "Station not found."})

    # -------------------- FARE DETAILS --------------------
    if "fare" in msg or "price" in msg or "ticket" in msg:
        train_no = "".join(re.findall(r'\d+', msg))

        cur.execute("SELECT * FROM fares WHERE train_no=%s", (train_no,))
        fares = cur.fetchall()

        if not fares:
            return jsonify({"reply": "No fare details found."})

        reply = f"💰 **Fare details for Train {train_no}:**\n\n"
        for f in fares:
            reply += f"◾ {f['class']} : ₹{f['fare']}\n"

        return jsonify({"reply": reply})

    # -------------------- TRAIN STOPS --------------------
    if "stops" in msg or "route" in msg:
        train_no = "".join(re.findall(r'\d+', msg))

        cur.execute("""
            SELECT * FROM train_stops 
            WHERE train_no=%s ORDER BY stop_no
        """, (train_no,))

        stops = cur.fetchall()

        if not stops:
            return jsonify({"reply": "No stops found."})

        reply = f"🛤 **Route for Train {train_no}:**\n\n"
        for s in stops:
            reply += f"{s['stop_no']}. {s['station_code']} — Arr: {s['arrival']} | Dep: {s['departure']}\n"

        return jsonify({"reply": reply})

    # -------------------- DEFAULT --------------------
    return jsonify({
        "reply": "I didn't understand that. Try:\n"
                 "• Guntur to Chennai\n"
                 "• Vijayawada to Bangalore\n"
                 "• 12604 fare\n"
                 "• 12604 stops\n"
                 "• Guntur station"
    })


# -------------------- LOGOUT --------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# -------------------- RUN APP --------------------
if __name__ == "__main__":
    app.run(debug=True)
