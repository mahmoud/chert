# TODO

* File format for short-form posts (yaml with explicit content
  field). Generic approach: if content field is not defined, expect
  the next document in the file to contain the content. If content
  field is defined, then the next document, if present, is a separate
  post.

* Support for non-root-path-based installations

* Make ToC style (numbered or bullets) configurable on a per-post
  basis (some posts, e.g., myths of python) may have internal numbers
  and that would look strange)

* superfeedr integration (pulled from PythonDoesBlog?)

* Data pages (YAML files that get rendered to markdown at load time)

* https canonical urls (should feed ID, etc. be scheme-less?)

* logs directory (+ add gitignore and note in scaffold README)

* Some sort of internal linking shorthand, i.e., make linking to other
  entries easy (markdown.extensions.wikilinks?)

* Global links and abbreviations appended to the Markdown source of
  all posts before rendering (abbreviations powered by
  markdown.extensions.abbr)

* Data file generation
  * markdown posts should generate a data file with all the links

* Add links to various files in the render context
  * Source
  * Standardized Source
  * HTML
  * Text
