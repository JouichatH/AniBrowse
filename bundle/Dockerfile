FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY . /viu
ENV PATH=/root/.local/bin:$PATH
WORKDIR /viu
RUN uv tool install .
CMD ["bash"]
