FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY payco ./payco
ENV PAYCO_DB=/data/payco/deliveries.db
EXPOSE 8000
CMD ["uvicorn", "--factory", "payco.main:app", "--host", "0.0.0.0", "--port", "8000"]
