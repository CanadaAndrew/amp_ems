import base64
import datetime
from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import requests

load_dotenv()

app = Flask(__name__)

# Function to get the connector for the DB
def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPW"),
        database="amptier_ems"
    )
    return connection

def fetch_all_reports(conn):
    # Fetching recent reports to display, getting all reports
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT report_id, category, severity, descr, locat, t_period, resolved, admin_notes
        FROM Reports
        ORDER BY t_period DESC
                   """)
    reports = cursor.fetchall()

    #Changing the Timestamp format for readability
    for report in reports:
        report["t_diff"] = datetime.datetime.now() - report["t_period"]
        if report["t_diff"].days > 0:
            report["t_diff"] = f"{report['t_diff'].days} days ago"
        elif report["t_diff"].seconds // 3600 > 0:
            report["t_diff"] = f"{report['t_diff'].seconds // 3600} hours ago"
        else:
            report["t_diff"] = f"{report['t_diff'].seconds // 60} minutes ago"

    #Changing the resolved status for readability
    for report in reports:
        report["resolved"] = "Resolved" if report["resolved"] else "Not Resolved"
    cursor.close()
    return reports

def fetch_recent_reports(conn, yesterdays_date):
    # Fetching recent reports to display, getting at max 10 reports from the last 24 hours
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT report_id, category, severity, descr, locat, t_period, resolved, admin_notes
        FROM Reports
        WHERE t_period >= %s
        ORDER BY t_period DESC
        LIMIT 10
                   """, (str(yesterdays_date),))
    reports = cursor.fetchall()

    #Changing the Timestamp format for readability
    for report in reports:
        report["t_diff"] = datetime.datetime.now() - report["t_period"]
        if report["t_diff"].days > 0:
            report["t_diff"] = f"{report['t_diff'].days} days ago"
        elif report["t_diff"].seconds // 3600 > 0:
            report["t_diff"] = f"{report['t_diff'].seconds // 3600} hours ago"
        else:
            report["t_diff"] = f"{report['t_diff'].seconds // 60} minutes ago"

    #Changing the resolved status for readability
    for report in reports:
        report["resolved"] = "Resolved" if report["resolved"] else "Not Resolved"
    cursor.close()
    return reports

def fetch_user_reports(conn, user_id):
    # Fetching all user reports to display.
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT report_id, category, severity, descr, locat, t_period, resolved, admin_notes
        FROM Reports
        WHERE user_id = %s
        ORDER BY t_period DESC
                   """, (str(user_id),))
    reports = cursor.fetchall()

    #Changing the Timestamp format for readability
    for report in reports:
        report["t_diff"] = datetime.datetime.now() - report["t_period"]
        if report["t_diff"].days > 0:
            report["t_diff"] = f"{report['t_diff'].days} days ago"
        elif report["t_diff"].seconds // 3600 > 0:
            report["t_diff"] = f"{report['t_diff'].seconds // 3600} hours ago"
        else:
            report["t_diff"] = f"{report['t_diff'].seconds // 60} minutes ago"

    #Changing the resolved status for readability
    for report in reports:
        report["resolved"] = "Resolved" if report["resolved"] else "Not Resolved"
    cursor.close()
    return reports

def fetch_report_images(conn, reports):
    #Fetching and attaching images for reports
    img_cursor = conn.cursor(dictionary=True)
    for report in reports:
        # Querying images for each report
        img_cursor.execute("""
            SELECT img, img_name, mime_type
            FROM Images
            WHERE report_id = %s
        """, (report["report_id"],))
        img_result = img_cursor.fetchall()
        if img_result:
            imgs = []
            for row in img_result:
                if row["img"]:
                    b64 = base64.b64encode(row["img"]).decode('ascii')
                    imgs.append({
                        "img_name": row["img_name"],
                        "mime_type": row["mime_type"],
                        "b64": b64
                    })
            report["images"] = imgs
    img_cursor.close()
    return reports

def fetch_weather():
    # Getting the weather and current time for the location
    city = "Sacramento"
    weather_api_key = os.getenv("WeatherAPI")
    weather = {}
    try:
        res = requests.get("http://api.openweathermap.org/data/2.5/weather?q=%s&appid=%s&units=imperial" % (city, weather_api_key))
        if res.status_code == 200:
            data = res.json()
            weather = {
                "city": city,
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"]
            }
    except Exception as e:
        print(f"Error fetching weather data: {e}")
    return weather

def fetch_user_info(conn, login_info):
    user_info={
        "user_id": None,
        "user_name": "Anonymous"
    }
    login_cursor = conn.cursor(dictionary=True)
    login_cursor.execute("""
        SELECT user_id, user_name
        FROM Users
        WHERE user_name = %s AND pass = %s
    """, (login_info["username"], login_info["password"]))
    user = login_cursor.fetchone()
    if user:
        user_info["user_id"] = user["user_id"]
        user_info["user_name"] = login_info["username"]
    else:
        login_cursor.close()
        conn.close()
    login_cursor.close()
    return user_info

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/user/<user_id>", methods=["GET", "POST"])
def user(user_id = None):
    conn = get_db_connection()
    yesterdays_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    #Taking the information from the forms and validating user login
    user_name = "Anonymous"
    user_info = {
        "user_id": user_id,
        "user_name": user_name
    }
    if int(user_id) == 0:
        login_info = {
            "username": request.form.get("username"),
            "password": request.form.get("password")
        }
        user_info = fetch_user_info(conn, login_info)
        if user_info["user_id"] is None:
            return redirect(url_for("home"))
        else:
            user_id = user_info["user_id"]

    #Fetching recent reports
    reports = fetch_recent_reports(conn, yesterdays_date)

    #Fetching images for each report
    reports = fetch_report_images(conn, reports)

    #Fetching user reports if not anonymous
    user_reports = None
    if user_id != "1":
        user_reports = fetch_user_reports(conn, user_id)
        user_reports = fetch_report_images(conn, user_reports)
    conn.close()

    #Fetching weather data for Sacramento
    weather = fetch_weather()

    return render_template("user.html", reports=reports, user_reports=user_reports, weather=weather, current_time = datetime.datetime.now().strftime("%I:%M %p"), user_id=user_info["user_id"], user_name=user_info["user_name"])

@app.route("/submit_complaint", methods=["POST"])
def submit_complaint():
    report = {
        "user_id": request.form.get("ID"),
        "category": request.form.get("Category"),
        "severity": request.form.get("Severity"),
        "description": request.form.get("Description"),
        "location": request.form.get("Location"),
        "images": request.files.getlist("Images"),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")     
    }
    conn = get_db_connection()
    cursor = conn.cursor()

    # Creating the paramertized queries
    query = """
        INSERT INTO Reports(user_id, category, severity, descr, locat, t_period, resolved) 
        VALUES(%s, %s, %s, %s, %s, %s, %s)
    """

    img_query = """
        INSERT INTO Images(report_id, img, img_name, mime_type)
        VALUES(%s, %s, %s, %s)
    """
    try:
        #Inputing the report query, setting the params and then executing it.
        params = (
        int(report["user_id"]) if report["user_id"] else 0,
        report["category"],
        int(report["severity"]) if report["severity"] else 0,
        report["description"] or None,
        report["location"] or "Sacramento",
        report["timestamp"],
        False
        )
        cursor.execute(query, params)
        #Retrieving ID to put images in, if any.
        report_id = cursor.lastrowid

        for img in report["images"]:
            #Checking the image, seeing its filetype, creating a filename for it, and then reading its binary data to send to the DB.
            if img and getattr(img, 'filename', None):
                img_filename = secure_filename(img.filename)
                mime = img.mimetype or None
                img_data = img.read()
                cursor.execute(img_query, (report_id, img_data, img_filename, mime))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

    if(report["user_id"] == "1"):
        return redirect(url_for("user", user_id=1))
    else:
        return redirect(url_for("user", user_id=int(report["user_id"])))
    
@app.route("/admin", methods=["GET", "POST"])
def admin():
    conn = get_db_connection()
    user_id = 0
    #Taking the information from the forms and validating user login
    user_name = "Anonymous"
    user_info = {
        "user_id": user_id,
        "user_name": user_name
    }
    if int(user_id) == 0:
        login_info = {
            "username": request.form.get("username"),
            "password": request.form.get("password")
        }
        user_info = fetch_user_info(conn, login_info)
        if user_info["user_id"] is None:
            return redirect(url_for("home"))
        else:
            user_id = user_info["user_id"]

    reports = fetch_all_reports(conn)
    reports = fetch_report_images(conn, reports)
    
    conn.close()

    #Fetching weather data for Sacramento
    weather = fetch_weather()
    return render_template("admin.html", reports = reports,weather=weather, current_time = datetime.datetime.now().strftime("%I:%M %p"), user_id=user_info["user_id"], user_name=user_info["user_name"])

@app.route("/submit_user", methods=["POST"])
def submit_user():
    # Logic to handle user submission goes here
    pass

if __name__ == "__main__":
    app.run()