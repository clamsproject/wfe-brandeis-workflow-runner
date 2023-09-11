import json
import argparse
from pathlib import Path
from string import Template

def read_json(file):
    '''returns guids and container ids from json file'''
    f = open(file)
    data = json.load(f)
    return data['GUIDS'], data['ContainerIDs']

def write_containerfile(guids):
    '''writes Containerfile'''
    file_template = Template('''FROM python:3-slim-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /output_data
VOLUME /output_data

WORKDIR /app
RUN pip install --upgrade pip
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
RUN apt update && apt -y install curl
RUN apt update && apt install bash

COPY ./pipeline.sh /app/pipeline.sh
RUN chmod +x pipeline.sh
RUN tr -d \r < pipeline.sh > pipeline.sh

CMD ["/bin/bash", "pipeline.sh", "${guid_list}"]''')
    file_text = file_template.substitute(guid_list=" ".join([guid["type"]+":"+guid["guid"]+"."+guid["type"] for guid in guids]))
    file = Path("Containerfile")
    file.open('w').write(file_text)
    return

def write_service(container, index):
    '''generates a service to be used in the compose.yaml'''
    name = "app" + str(index)
    service_template = Template('''  ${name}:
    image: ${image}
    container_name: ${name}''')
    return name, service_template.substitute(name=name, image=container)

def write_bash(services):
    '''writes bash script that curls to apps in a given order'''
    curl_command = "|".join([" curl -d@- " + service + ":5000 " for service in services])
    bash_template = Template('''#!/bin/bash
for guid in $$1
do
    clams source --scheme baapb $$guid |${curl}> output_data/$$guid.out.mmif
done''')
    bash = bash_template.substitute(curl=curl_command)
    file = "app" / Path("pipeline.sh")
    file.open('w').write(bash)
    return

def write_compose(containers):
    '''given a list of containers, creates a compose.yaml file'''
    start = Template("""services:
  head:
    build:
      context: app
      dockerfile: ../Containerfile
    container_name: head
    depends_on:
      ${depend}
    volumes:
      - output_data:/output_data
${apps}
volumes:
  output_data:
    driver: local""")
    # TODO: add volume mount so that files are available on host system
    services = {}
    index = 1
    for container in containers:
        name, service = write_service(container, index)
        services[name] = service
        index += 1
    write_bash(services)
    compose_text = start.substitute(depend="\n      ".join("- " + service for service in services), apps="\n".join([services[service] for service in services]))
    file = Path("compose.yaml")
    file.open('w').write(compose_text)
    return

if __name__ == '__main__':
    p = Path("app")
    if not p.is_dir():
        p.mkdir(parents=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help="the request json file")
    args = parser.parse_args()
    guids, containers = read_json(args.filename)
    write_containerfile(guids)
    write_compose(containers)
    # TODO: possibly add feature to automate call to docker compose after the compose.yaml is created