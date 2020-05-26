all: copy-files

install:
	yarn install

minify: install
	./node_modules/.bin/uglifyjs --mangle --source-map test.map --source-map-include-sources --prefix relative --output test.min.js test.js

update: minify
	node launch.js

copy-files: update
	cp test.* ../js-images

.PHONY: all install minify update copy-files
