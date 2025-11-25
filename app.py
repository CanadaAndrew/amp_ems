import datetime
from flask import Flask, render_template, request, redirect, url_for
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/anonymous")
def anonymous():
    return render_template("anonymous.html")

@app.route("/submit_complaint", methods=["POST"])
def submit_complaint():
    report = {
        "user_id": request.form.get("ID"),
        "category": request.form.get("Category"),
        "severity": request.form.get("Severity"),
        "description": request.form.get("Description"),
        "location": request.form.get("Location"),
        "images": request.form.getlist("Images"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"        
    }
    if int(report["user_id"]) == 0:
        return redirect(url_for('anonymous'))
    else: 
        return redirect(url_for('home'))

if __name__ == "__main__":
    app.run()