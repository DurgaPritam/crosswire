# Build context: repo root (needs packages/wirecheck).
FROM python:3.12-slim
WORKDIR /srv
COPY evidence/payco-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/wirecheck /tmp/wirecheck
RUN pip install --no-cache-dir /tmp/wirecheck && rm -rf /tmp/wirecheck
COPY evidence/payco-mcp/payco_evidence ./payco_evidence
ENV PAYCO_DB=/data/payco/deliveries.db PAYCO_DOCS=/docs/webhooks.md PORT=7101
EXPOSE 7101
USER nobody
CMD ["python", "-m", "payco_evidence"]
