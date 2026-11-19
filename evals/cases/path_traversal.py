import os

from flask import Flask, request, send_file

app = Flask(__name__)
UPLOAD_DIR = "/srv/uploads"


@app.get("/download")
def download():
    name = request.args.get("file", "")
    return send_file(os.path.join(UPLOAD_DIR, name))
