# The approver: signs human approvals (see approver/approver/service.py). Build context: repo root.
FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "cryptography==43.0.3" "httpx==0.28.1"
COPY guards/disclosure_canon.py ./approver/disclosure_canon.py
COPY guards/ledger_chain.py ./approver/ledger_chain.py
COPY approver/approver ./approver
# the Switch agent protocol client, shared with the notary
COPY neutral/notary/notary/client.py ./approver/switch_client.py
COPY neutral/notary/notary/sse.py ./approver/sse.py
# the signing key and the signed approvals live in the `approver-data` volume, never on the host filesystem
ENV APPROVER_DATA=/data APPROVER_WS=/ws APPROVER_PORT=7400
CMD ["python", "-m", "approver"]
