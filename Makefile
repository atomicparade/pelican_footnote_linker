lint:
	black pelican/plugins/footnote_linker
	mypy --strict pelican/plugins/footnote_linker
	pylint pelican/plugins/footnote_linker

sample:
	cd sample; pelican --debug

.PHONY: lint test sample
