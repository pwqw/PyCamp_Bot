.PHONY: build run test all

build:
	docker build --rm -t pycamp_bot .

run:
	docker run --rm --env-file .env pycamp_bot

test:
	docker run --rm --env-file .env pycamp_bot pytest

all: build run

.DEFAULT_GOAL := all
