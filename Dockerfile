FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/question_papers storage/marking_schemes \
             storage/answer_sheets storage/reports

EXPOSE 5050 8501

ENV GEMINI_API_KEY=""
ENV FLASK_SECRET="change-me-in-production"

# Start both services via the shell script
CMD ["bash", "start.sh"]
