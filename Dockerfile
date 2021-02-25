FROM python:3.9

WORKDIR /wknc-bot

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]