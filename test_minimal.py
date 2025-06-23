#!/usr/bin/env python3
"""
Minimal test to isolate the incomplete response issue
"""
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello World - Basic Flask works!"

@app.route('/json')
def json_test():
    return jsonify({"status": "ok", "message": "JSON response works"})

@app.route('/template')
def template_test():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Template Test</title></head>
    <body><h1>Template rendering works!</h1></body>
    </html>
    """)

if __name__ == '__main__':
    app.run(debug=True)
