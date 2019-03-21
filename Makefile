ORG=seequent
APP=lfview-api-client
MODULE=lfview

.PHONY: build build27 run notebooks-docker notebooks tests tests27 \
	docs lint-yapf lint-pylint publish

build:
	docker build -t $(ORG)/$(APP):latest -f Dockerfile .

build27:
	docker build -t $(ORG)/$(APP):latest27 -f Dockerfile.27 .

run: build
	docker run -it --rm \
		--name=$(APP) \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		$(ORG)/$(APP):latest \
		ipython

notebooks-docker: build
	docker run -it --rm \
		--name=$(APP)-notebooks \
		-p 127.0.0.1:8888:8888 \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/notebooks:/usr/src/app/notebooks \
		$(ORG)/$(APP):latest \
		python -m notebook /usr/src/app/notebooks --ip 0.0.0.0 --port 8888 --allow-root

notebooks-local:
	python -m notebook $(shell pwd)/notebooks --ip 0.0.0.0 --port 8888 --allow-root

tests: build
	mkdir -p cover
	docker run -it --rm \
		--name=$(APP)-tests \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/tests:/usr/src/app/tests \
		-v $(shell pwd)/cover:/usr/src/app/cover \
		$(ORG)/$(APP):latest \
		bash -c "pytest --cov=$(MODULE) --cov-report term --cov-report html:cover tests/ && mv .coverage cover/.coverage"
	mv -f cover/.coverage ./

tests27: build27
	docker run -it --rm \
		--name=$(APP)-tests \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/tests:/usr/src/app/tests \
		$(ORG)/$(APP):latest27 \
		bash -c "pytest tests/"

docs: build
	docker run -it --rm \
		--name=$(APP)-docs \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/docs:/usr/src/app/docs \
		$(ORG)/$(APP):latest \
		bash -c "cd docs && make html"

lint-yapf: build
	docker run -it --rm \
		--name=$(APP)-tests \
		-v $(shell pwd)/.style.yapf:/usr/src/app/.style.yapf \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/tests:/usr/src/app/tests \
		$(ORG)/$(APP):latest \
		yapf -rd $(MODULE) tests

lint-pylint: build
	docker run -it --rm \
		--name=$(APP)-tests \
		-v $(shell pwd)/.pylintrc:/usr/src/app/.pylintrc \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/tests:/usr/src/app/tests \
		$(ORG)/$(APP):latest \
		pylint --rcfile=.pylintrc $(MODULE) tests

publish: build
	mkdir -p dist
	docker run -it --rm \
		--name=$(APP)-publish \
		-v $(shell pwd)/$(MODULE):/usr/src/app/$(MODULE) \
		-v $(shell pwd)/dist:/usr/src/app/dist \
		$(ORG)/$(APP) \
		python setup.py sdist bdist_wheel
	pip install twine
	twine upload dist/*
