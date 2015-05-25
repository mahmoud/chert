# TODO

* Look for a user-controlled module that is imported/executed and
  converted into values available in the render context. This way
  users can customize themes to include custom computable values.

* How to set ID for the feed and entries such that they remain stable?
  Is canonical URL sufficient?

* File format for short-form posts (yaml with explicit content
  field). Generic approach: if content field is not defined, expect
  the next document in the file to contain the content. If content
  field is defined, then the next document, if present, is a separate
  post.

* Finish support for non-root-path-based installations

* --clean option (effectively removes any unused files from site/)

* Make ToC style (numbered or bullets) configurable on a per-post
  basis (some posts, e.g., myths of python) may have internal numbers
  and that would look strange)

* analytics code in config

* superfeedr integration (pulled from PythonDoesBlog?)

* Data pages (YAML files that get rendered to markdown at load time)

* https canonical urls (should feed ID, etc. be scheme-less?)

* make loads idempotent instead of explicit reset (was getting
  duplicates in EntryLists on server reload)
