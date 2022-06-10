all: release

test:
	@echo Running tests...
	python -m tests.all

clean:
	@echo Cleaning...
	-rm -r ./build
	-rm -r ./dist

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
