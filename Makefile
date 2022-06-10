all: release

test:
	@echo Running tests...
	python -m tests.all

clean:
	@echo Cleaning...
	-rm -r ./build
	-rm -r ./dist
	-rm -r ./__pycache__
	-rm -r ./RNS/__pycache__
	-rm -r ./RNS/Cryptography/__pycache__
	-rm -r ./RNS/Cryptography/aes/__pycache__
	-rm -r ./RNS/Cryptography/pure25519/__pycache__
	-rm -r ./RNS/Interfaces/__pycache__
	-rm -r ./RNS/Utilities/__pycache__
	-rm -r ./RNS/vendor/__pycache__
	-rm -r ./RNS/vendor/i2plib/__pycache__
	-rm -r ./tests/__pycache__
	-rm -r ./tests/rnsconfig/storage

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

release: remove_symlinks build_wheel build_pure_wheel create_symlinks

upload:
	@echo Ready to publish release, hit enter to continue
	@read VOID
	@echo Uploading to PyPi...
	twine upload dist/*
	@echo Release published
