# Todos los comandos (bot, tests, etc.) se ejecutan dentro del contenedor.
# Requiere imagen construida (make build) y .env para run/test.

.PHONY: build run test test-cov all

build:
	docker build --rm -t pycamp_bot .

run:
	docker run --rm --env-file .env pycamp_bot

test:
	docker run --rm --env-file .env pycamp_bot pytest

test-cov:
	docker run --rm --env-file .env pycamp_bot pytest --cov=pycamp_bot --cov-report=term-missing

all: build run

.DEFAULT_GOAL := all
