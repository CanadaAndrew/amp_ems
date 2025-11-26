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

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user=os.getenv("DBUSER"),
        password=os.getenv("DBPW"),
        database="amptier_ems"
    )
    return connection

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/anonymous")
def anonymous():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    yesterdays_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    # Fetching recent reports to display, getting all reports from the last 24 hours
    cursor.execute("""
        SELECT report_id, category, severity, descr, locat, t_period, resolved
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

    #Fetching and attaching images for reports
    img_cursor = conn.cursor(dictionary=True)
    for report in reports:
        # Querying images for each report
        cursor.execute("""
            SELECT img, img_name, mime_type
            FROM Images
            WHERE report_id = %s
        """, (report["report_id"],))
        img_result = cursor.fetchall()
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
    cursor.close()
    conn.close()

    # Getting the weather and current time for the location
    city = "Sacramento"
    weather_api_key = os.getenv("WeatherAPI")
    weather = {}
    try:
        res = requests.get("http://api.openweathermap.org/data/2.5/weather?q=%s&appid=%s&units=imperial" % (city, weather_api_key))
        if res.status_code == 200:
            data = res.json()
            print(data)
            weather = {
                "city": city,
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"]
            }
            print(weather)
    except Exception as e:
        print(f"Error fetching weather data: {e}")

    return render_template("anonymous.html", reports=reports, weather=weather, current_time = datetime.datetime.now().strftime("%I:%M %p"))

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

    if(report["user_id"] == "0"):
        return redirect(url_for("anonymous"))
    else:
        return redirect(url_for("home"))

if __name__ == "__main__":
    app.run()