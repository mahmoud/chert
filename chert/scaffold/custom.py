# user customization
# TODO: document other hooks

print ' - custom module loaded.'


def chert_on_load(chert_obj):
    print ' - on_load hook: %s entries loaded' % len(chert_obj.entries)
