FROM python:3.10-slim-bullseye

EXPOSE 8080

RUN apt update && apt upgrade -y
RUN apt install git -y
COPY requirements.txt /requirements.txt

RUN pip3 install -U pip && pip3 install -U -r requirements.txt
RUN mkdir /telegram-session-bot
WORKDIR /telegram-session-bot
COPY . /telegram-session-bot
CMD ["python", "bot.py"]
