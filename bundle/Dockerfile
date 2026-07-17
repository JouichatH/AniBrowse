FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY . /ani-browse
ENV PATH=/root/.local/bin:$PATH
WORKDIR /ani-browse
RUN uv tool install .
CMD ["bash"]
