# user customization
# TODO: document other hooks

print ' - custom module loaded.'


def chert_post_load(chert_obj):
    print ' - post_load hook: %s entries loaded' % len(chert_obj.entries)
