
.PHONY: run test build

build:
	docker-compose build
run: build
	docker-compose run cmd
down:
	docker-compose down

test: build
	docker-compose run cmd python setup.py test; docker-compose down

