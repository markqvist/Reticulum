# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@if [ $@ = "html" ]; then \
		rm -rf html; \
		rm -rf manual; \
		cp -r build/html ./; \
		mv html manual; \
		echo "HTML Manual Generated"; \
	fi

	@if [ $@ = "latexpdf" ]; then \
		cp -r build/latex/reticulumnetworkstack.pdf ./Reticulum\ Manual.pdf; \
		echo "PDF Manual Generated"; \
	fi

	@if [ $@ = "epub" ]; then \
		cp -r build/epub/ReticulumNetworkStack.epub ./Reticulum\ Manual.epub; \
		echo "EPUB Manual Generated"; \
	fi
