FROM python:3.8-slim

RUN apt-get update \
    && apt-get install -y python3 python3-pip

RUN python3 -m pip install pyarrow \
    && python3 -m pip install pandas \
    && python3 -m pip install faker

ADD client.py /root
ADD do_get.sh /root

CMD ["sleep", "1d"]
