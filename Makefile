lint:
	black pelican/plugins/footnote_linker
	mypy --strict pelican/plugins/footnote_linker
	pylint pelican/plugins/footnote_linker

.PHONY: lint
