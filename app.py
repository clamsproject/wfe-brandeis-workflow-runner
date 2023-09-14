import argparse
from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def main():
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', nargs='?', help="the host name", default="0.0.0.0")
    parser.add_argument('--port', nargs='?', help="the port to run the app from", default="9000")
    args = parser.parse_args()
    HOST = args.host
    PORT = args.port
    app.run(host=HOST, port=PORT)