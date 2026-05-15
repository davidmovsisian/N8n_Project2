FROM docker.n8n.io/n8nio/n8n

USER root

# Install Python and dependencies
RUN apk add --no-cache python3 py3-pip \
    && pip3 install --no-cache-dir pymupdf python-docx pdfplumber --break-system-packages

# Copy extraction scripts
COPY src/ /home/node/src/

USER node 