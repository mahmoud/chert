
## Starting

* Read the README.md in this directory for an introduction to the
  directory structure of a Chert site.
* Run `git init` or other version control initialization commands in
  the directory containing this TODO.
  * Tweak the included `.gitignore` if need be.
  * Perform your first `git commit`!
* Set the title, tagline, and author name in `config.yaml`
  * Update the links with the relevant social media stuff

## Authoring

* Put any non-entry media, such as graphics and photos under the
  `uploads` directory
* Write a new entry under the `entries` directory
  * Markdown reference: https://guides.github.com/features/mastering-markdown/
  * YAML reference: https://en.wikipedia.org/wiki/YAML#Sample_document
* After you've got a basic post, view it by running `chert serve` in
  the same directory as this TODO. Whenever you edit your post, hit
  save and then refresh your browser to see the new version.
* Update the `entries/about.md` special entry with information about you.

## Customizing

* Put custom behaviors in custom.py
* Optionally change the development server port/ip under the dev
  section of config.yaml
* Tweak the theme under the `theme` directory
  * Dust references: http://akdubya.github.io/dustjs/ &
    https://github.com/linkedin/dustjs/wiki/Dust-Tutorial

## Publishing

* Procure a server
* Save the relevant details (host, username, path) under the `prod`
  section of `config.yaml`
* Set up SSH keys
* Ensure rsync is installed on the local machine
* Run `chert publish`
