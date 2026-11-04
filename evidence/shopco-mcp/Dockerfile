# Build context: repo root (needs packages/wirecheck).
FROM python:3.12-slim
WORKDIR /srv
COPY evidence/shopco-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/wirecheck /tmp/wirecheck
RUN pip install --no-cache-dir /tmp/wirecheck && rm -rf /tmp/wirecheck
COPY evidence/shopco-mcp/shopco_evidence ./shopco_evidence
ENV SHOPCO_DB=/data/shopco/jobs.db PORT=7102
EXPOSE 7102
USER nobody
CMD ["python", "-m", "shopco_evidence"]
