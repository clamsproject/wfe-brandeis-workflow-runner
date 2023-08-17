from flask import Flask, request
from datetime import datetime
from pathlib import Path
import random
import string
import subprocess
import os
import json
import argparse
from clams import source
from mmif import Mmif, DocumentTypes
import requests
import time

app = Flask(__name__)

def request_id():
    '''generates random hash id'''
    hash = ''.join(random.choice(string.ascii_letters) for i in range(10))
    return datetime.today().strftime("%y%m%d%H%M%S") + "_" + hash

def read_json(file):
    '''returns guids and container ids from json file'''
    f = open(file)
    data = json.load(f)
    return data['GUIDS'], data['ContainerIDs']

def generate_source(guids):
    '''generates source mmif given guids and file types'''
    file_names = [guid["type"]+":"+guid["guid"]+"."+guid["type"] for guid in guids]
    mmif = source.generate_source_mmif_from_customscheme(file_names, "baapb")
    print(mmif)
    return Mmif(mmif)

def update_input(input):
    '''updates input.mmif'''
    file = Path('input.mmif')
    file.open('w').write(input)
    print("updating input")
    return

def run_container(id, port_index):
    '''runs a docker container and returns its id'''
    print("starting to run container: " + id)
    print()
    environment_argument = "BAAPB_RESOLVER_ADDRESS=eldrad.cs-i.brandeis.edu:23456"
    port_argument = str(port_index) + ":5000"
    mount_argument = "/mnt:/mnt"
    container_id = subprocess.run([CONTAINER_CMD, "run", '-d', "--rm", "-e", environment_argument, "-p", port_argument, "-v", mount_argument, id, "/bin/bash", "-c", 'pip3 install mmif-docloc-baapb && python3 /app/app.py'], stdout=subprocess.PIPE, text=True)
    # add feature to support bigger containers (loop until get request returns 200?)
    return container_id.stdout
    
def get_result(port_index):
    '''given a port, gets the result of posting input.mmif to that port'''
    url_argument = "http://" + "127.0.0.1" + ":" + str(port_index)
    result = requests.post(url_argument, data=open("input.mmif").read())
    return result.text

def close_containers(docker_ids):
    '''closes containers'''
    for id in docker_ids:
        subprocess.run([CONTAINER_CMD, "stop", id.split()[0]])
    return

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
    start_port_index = 35010
    end_port_index = 35010
    update_input(generate_source(guids).serialize())
    i = 0
    container_list = []
    while i < len(container_ids):
        container_list.append(run_container(container_ids[i], end_port_index))
        i += 1
        end_port_index += 1
    time.sleep(15)
    for i in range(start_port_index, end_port_index):
        update_input(get_result(i))
    close_containers(container_list)
    write_output(open('input.mmif').read(), id) 
    return "complete"

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', nargs='?', help="the host name", default="0.0.0.0")
    parser.add_argument('--port', nargs='?', help="the port", default="35000")
    container = parser.add_mutually_exclusive_group(required=True)
    container.add_argument('--docker', action='store_true', help='use docker to run the containers')
    container.add_argument('--podman', action='store_true', help='use podman to run the containers')
    args = parser.parse_args()
    HOST = args.host
    PORT = args.port
    CONTAINER_CMD = "docker"
    if args.podman:
        CONTAINER_CMD = "podman"
    app.run(host=HOST, port=PORT)
    