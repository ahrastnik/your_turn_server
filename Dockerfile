FROM python:3.11

WORKDIR /root/.
COPY requirements.txt .
COPY your_turn.py .

EXPOSE 6969/udp

RUN pip install -r requirements.txt

CMD ["python", "your_turn.py"]
