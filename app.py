from flask import Flask, request
from datetime import datetime
from pathlib import Path
import random
import string
import subprocess
import os
import json
import argparse
from mmif import Mmif, DocumentTypes

app = Flask(__name__)

def request_id():
    '''generates random hash id'''
    hash = ''.join(random.choice(string.ascii_letters) for i in range(10))
    return hash + "_" + datetime.today().strftime("%y%m%d%H%M%S")

def read_json(file):
    '''returns guids and container ids from json file'''
    f = open(file)
    data = json.load(f)
    return data['GUIDS'], data['ContainerIDS']

def generate_source(guids):
    '''given list of dictionaries, with each dictionary containing a guid and file type, generates a source MMIF (assuming baapb scheme)'''
    types = {
        'video': DocumentTypes.VideoDocument,
        'audio': DocumentTypes.AudioDocument,
        'text': DocumentTypes.TextDocument,
        'image': DocumentTypes.ImageDocument
    }
    documents = []
    index = 1
    for guid in guids:
        file_location = "baapb://" + guid["guid"] + "." + guid["type"]
        document = '''{"@type": "''' + types[guid["type"]] + '''", "properties": { "id": "d''' + str(index) + '''", "mime": "''' + guid["type"] + '''", "location": "''' + file_location + '''"}}'''
        index += 1
        documents.append(document)
    mmif_str = """{
                    "metadata": {
                        "mmif": "http://mmif.clams.ai/1.0.2"
                    },
                    "documents": [
                    """
    i = 0
    while i < len(documents) - 1:
        mmif_str = mmif_str + documents[i] + ","
        i += 1
    mmif_str = mmif_str + documents[i] + '''], "views": []}'''
    return Mmif(mmif_str)

def pull_images(container_ids):
    '''builds docker images'''
    for id in container_ids:
        subprocess.run(["docker", "pull"], input=id)
    return

def update_input(input):
    '''updates input.mmif'''
    file = Path('input.mmif')
    file.open('w').write(input)
    return

def run_container(id, port_index):
    '''runs a docker container and returns the result'''
    port_argument = "-p=" + str(port_index) + ":5000"
    mount_argument = "-v=" + DIRECTORY + ":/data"
    subprocess.run(["docker", "run", "--rm", port_argument, mount_argument, id])
    port_argument = "http://" + HOST + ":" + PORT
    result = subprocess.run(["curl", "-H", "Accept: application/json", "-X", "POST", "-d@input.mmif", port_argument], stdout=subprocess.PIPE, text=True)
    return result.stdout

def write_output(output, id):
    '''writes output in directory named after request id'''
    Path(id).mkdir(parents=True)
    file = str(id) / Path('output.mmif')
    file.open('w').write(output)
    return

@app.route('/pipeline', methods=['POST'])
def pipeline():
    id = request_id()
    guids, container_ids = read_json(request.form['request'])
    port_index = 5001
    update_input(generate_source(guids))
    update_input(input)
    pull_images(container_ids)
    i = 0
    while i < len(container_ids) - 1:
        update_input(run_container(container_ids[i], port_index))
        i += 1
        port_index += 1
    output = run_container(container_ids[i], port_index)
    write_output(output, id)    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', nargs='?', help="the host name", default="0.0.0.0")
    parser.add_argument('--port', nargs='?', help="the port", default="5000")
    parser.add_argument('--directory', nargs='?', help="the directory containing the AAPB files", default="../../llc_data/clams")
    parser.add_argument('--variable', nargs='?', help="the environment variable storing the location of the BAAPB server", default="BAAPB_RESOLVER_ADDRESS")
    args = parser.parse_args()
    HOST = args.host
    PORT = args.port
    DIRECTORY = args.directory
    RESOLVER_ADDRESS = os.envrion[args.variable]
    app.run(host=HOST, port=PORT)
    