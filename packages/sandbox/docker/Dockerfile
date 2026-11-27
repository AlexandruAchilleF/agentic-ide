FROM python:3.12-slim

RUN pip install --no-cache-dir pytest

RUN useradd --create-home --uid 1000 user1

WORKDIR /work

USER user1
