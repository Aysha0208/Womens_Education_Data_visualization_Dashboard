from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import requests
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "women-education-dashboard-secret"

DB = "database.db"
INDICATOR = "SE.ADT.LITR.FE.ZS"
API_URL = f"https://api.worldbank.org/v2/country/all/indicator/{INDICATOR}"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS visitors(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        page TEXT,
        visit_time TEXT
    )""")
    con.execute(
        "INSERT OR IGNORE INTO users(email,password) VALUES(?,?)",
        ("admin@gmail.com", "admin123")
    )
    con.commit()
    con.close()

def log_visit(page):
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT INTO visitors(email,page,visit_time) VALUES(?,?,?)",
        (session.get("email", "Guest"), page,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    con.commit()
    con.close()

def fetch_world_bank():
    try:
        r = requests.get(
            API_URL,
            params={"format": "json", "per_page": 20000},
            timeout=20
        )
        r.raise_for_status()
        payload = r.json()
        rows = []

        if isinstance(payload, list) and len(payload) > 1:
            for item in payload[1]:
                value = item.get("value")
                country = item.get("country", {}).get("value")
                if value is not None and country:
                    rows.append({
                        "country": country,
                        "country_code": item.get("countryiso3code", ""),
                        "year": int(item["date"]),
                        "percentage": round(float(value), 2)
                    })

        df = pd.DataFrame(
            rows,
            columns=["country", "country_code", "year", "percentage"]
        )

        if not df.empty:
            os.makedirs("data", exist_ok=True)
            df.to_csv("data/education_data.csv", index=False)
            return df, True

    except Exception as e:
        print("Live data unavailable:", e)

    return pd.DataFrame(), False

def get_data():
    live, is_live = fetch_world_bank()

    if is_live:
        return live, True

    path = "data/education_data.csv"
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                return df, False
        except Exception as e:
            print("CSV error:", e)

    return pd.DataFrame(
        columns=["country", "country_code", "year", "percentage"]
    ), False

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        con = sqlite3.connect(DB)
        user = con.execute(
            "SELECT id FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        con.close()

        if user:
            session["logged_in"] = True
            session["email"] = email
            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password"
        )

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    log_visit("Dashboard")
    df, is_live = get_data()

    countries = []
    years = []

    if not df.empty:
        countries = sorted(df["country"].dropna().unique().tolist())
        years = sorted(
            [int(x) for x in df["year"].dropna().unique()],
            reverse=True
        )

    latest_year = int(df["year"].max()) if not df.empty else "N/A"
    latest = df[df["year"] == latest_year] if not df.empty else pd.DataFrame()

    return render_template(
        "dashboard.html",
        countries=countries,
        years=years,
        total=int(latest["country"].nunique()) if not latest.empty else 0,
        average=round(latest["percentage"].mean(), 2) if not latest.empty else 0,
        highest=round(latest["percentage"].max(), 2) if not latest.empty else 0,
        lowest=round(latest["percentage"].min(), 2) if not latest.empty else 0,
        latest_year=latest_year,
        is_live=is_live
    )

@app.route("/countries")
def countries():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    log_visit("Countries")
    df, is_live = get_data()

    country_list = []
    if not df.empty:
        latest_year = int(df["year"].max())
        latest = df[df["year"] == latest_year].sort_values(
            "percentage", ascending=False
        )
        country_list = latest.to_dict(orient="records")

    return render_template(
        "countries.html",
        countries=country_list,
        is_live=is_live
    )

@app.route("/visitors")
def visitors():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    log_visit("Visitors")
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT email,page,visit_time FROM visitors ORDER BY id DESC"
    ).fetchall()
    con.close()

    return render_template("visitors.html", rows=rows)

@app.route("/api/data")
def api_data():
    df, is_live = get_data()

    country = request.args.get("country", "").strip()
    year = request.args.get("year", "").strip()

    if not df.empty and country:
        df = df[df["country"].str.lower() == country.lower()]

    if not df.empty and year:
        try:
            df = df[df["year"] == int(year)]
        except ValueError:
            pass

    return jsonify({
        "live": is_live,
        "source": "World Bank / UNESCO" if is_live else "Offline preview CSV",
        "records": df.to_dict(orient="records")
    })

@app.route("/api/summary")
def api_summary():
    df, is_live = get_data()

    if df.empty:
        return jsonify({"live": is_live, "records": []})

    latest_year = int(df["year"].max())
    latest = df[df["year"] == latest_year].copy()
    latest = latest.sort_values("percentage", ascending=False)

    top = latest.head(10)
    bottom = latest.tail(5).sort_values("percentage")

    # Global trend uses all available observations by year.
    trend = (
        df.groupby("year", as_index=False)["percentage"]
        .mean()
        .sort_values("year")
    )

    return jsonify({
        "live": is_live,
        "source": "World Bank / UNESCO" if is_live else "Offline preview CSV",
        "latest_year": latest_year,
        "total_countries": int(latest["country"].nunique()),
        "average": round(float(latest["percentage"].mean()), 2),
        "highest": round(float(latest["percentage"].max()), 2),
        "lowest": round(float(latest["percentage"].min()), 2),
        "top10": top.to_dict(orient="records"),
        "bottom5": bottom.to_dict(orient="records"),
        "trend": trend.to_dict(orient="records"),
        "all_latest": latest.to_dict(orient="records")
    })

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
