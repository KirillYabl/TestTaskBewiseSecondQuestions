FROM python:3.9.16-slim-buster

RUN apt update && apt install -y ffmpeg libavcodec-extra

WORKDIR /src

COPY requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /src/requirements.txt

COPY src /src

CMD ["python3", "server.py"]