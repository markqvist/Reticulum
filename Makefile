all: release

test:
	@echo Running tests...
	python3 -m tests.all

clean:
	@echo Cleaning...
	@-rm -rf ./build
	@-rm -rf ./dist
	@-rm -rf ./*.data
	@-rm -rf ./__pycache__
	@-rm -rf ./RNS/__pycache__
	@-rm -rf ./RNS/Cryptography/__pycache__
	@-rm -rf ./RNS/Cryptography/aes/__pycache__
	@-rm -rf ./RNS/Cryptography/pure25519/__pycache__
	@-rm -rf ./RNS/Interfaces/__pycache__
	@-rm -rf ./RNS/Utilities/__pycache__
	@-rm -rf ./RNS/vendor/__pycache__
	@-rm -rf ./RNS/vendor/i2plib/__pycache__
	@-rm -rf ./tests/__pycache__
	@-rm -rf ./tests/rnsconfig/storage
	@-rm -rf ./*.egg-info
	@make -C docs clean
	@echo Done

remove_symlinks:
	@echo Removing symlinks for build...
	-rm Examples/RNS
	-rm RNS/Utilities/RNS

create_symlinks:
	@echo Creating symlinks...
	-ln -s ../RNS ./Examples/
	-ln -s ../../RNS ./RNS/Utilities/

build_sdist_only:
	python3 setup.py sdist

build_wheel:
	python3 setup.py sdist bdist_wheel

build_pure_wheel:
	python3 setup.py sdist bdist_wheel --pure

documentation:
	make -C docs html

manual:
	make -C docs latexpdf epub

release: test remove_symlinks build_wheel build_pure_wheel documentation manual create_symlinks

debug: remove_symlinks build_wheel build_pure_wheel create_symlinks

upload:
	@echo Ready to publish release, hit enter to continue
	@read VOID
	@echo Uploading to PyPi...
	twine upload dist/*
	@echo Release published
