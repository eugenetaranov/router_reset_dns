from flask import Flask
from flask import request
import json


LOG_FILE="/logs/data.log"

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def default():
    if request.method == "GET":
        return "OK"
    elif request.method == "POST":
        data = request.form
        data = json.dumps(data)

        with open(LOG_FILE, "a") as f:
            f.write(f"{data}\n")

        return ""
