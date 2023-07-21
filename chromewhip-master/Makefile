.PHONY: release
release:
	git checkout master
	git pull
	py.test
	bumpversion patch
	python setup.py sdist bdist_wheel upload
	git push origin master --tags

.PHONY: regenerate
regenerate:
	cd scripts && ./regenerate_protocol.sh
