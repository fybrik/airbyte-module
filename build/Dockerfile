FROM python:3.9-slim

ENV USER_UID=1001 \
    USER_NAME=abm

COPY  build/bin /usr/local/bin
RUN  /usr/local/bin/user_setup

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY main.py main.py
COPY abm abm

RUN apt-get update
RUN apt-get install -y docker.io curl

EXPOSE 8080 8081

ENTRYPOINT ["python3"]
CMD ["main.py"]

USER ${USER_UID}

