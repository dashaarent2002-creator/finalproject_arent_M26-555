install:
	uv sync

project:
	uv run project

build:
	uv build

publish:
	uvx twine check dist/*

package-install:
	uv tool install --force dist/*.whl

lint:
	uv run ruff check .
