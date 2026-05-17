# Stage 1: Install Python packages on matching Alpine version
FROM python:3.12-alpine3.22 AS python-builder

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt --target /packages

# Stage 2: n8n with Python
FROM docker.n8n.io/n8nio/n8n

USER root

# Copy Python interpreter and standard library
COPY --from=python-builder /usr/local/bin/python3.12 /usr/local/bin/python3.12
COPY --from=python-builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=python-builder /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/libpython3.12.so.1.0
RUN ln -sf /usr/local/bin/python3.12 /usr/local/bin/python3 \
    && ln -sf /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/libpython3.12.so

# Copy installed packages
COPY --from=python-builder /packages /packages
ENV PYTHONPATH=/packages
ENV LD_LIBRARY_PATH=/usr/local/lib

# Copy extraction scripts
COPY src/ /home/node/src/

USER node