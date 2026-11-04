# Build context: repo root (needs packages/wirecheck). Run with `docker compose --profile notary up notary`.
FROM python:3.12-slim
WORKDIR /srv
COPY neutral/notary/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/wirecheck /tmp/wirecheck
RUN pip install --no-cache-dir /tmp/wirecheck && rm -rf /tmp/wirecheck
COPY neutral/notary/notary ./notary
# credentials and state are mounted at runtime, never baked into the image
ENV NOTARY_CREDENTIALS=/run/notary/.credentials.json NOTARY_STATE=/run/notary/.state.json
CMD ["python", "-m", "notary"]
