from flask import Flask
from flask import request

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def default():
    if request.method == "GET":
        return "OK"
    elif request.method == "POST":
        data = request.form
        print(data)
        return data
