FROM python:3.12-slim-bookworm

LABEL maintainer="H&Rsolucionesweb.com"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/project/src

WORKDIR /project

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY . /project

RUN useradd \
        --create-home \
        --shell /bin/bash \
        data-user \
    && chown -R data-user:data-user /project

USER data-user

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]