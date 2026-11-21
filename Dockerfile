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

COPY docker-entrypoint.sh /usr/local/bin/data-health-entrypoint

RUN useradd \
        --create-home \
        --shell /bin/bash \
        data-user \
    && chown -R data-user:data-user /project \
    && chmod 0755 /usr/local/bin/data-health-entrypoint

USER data-user

EXPOSE 8501

ENTRYPOINT ["data-health-entrypoint"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--global.developmentMode=false", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
