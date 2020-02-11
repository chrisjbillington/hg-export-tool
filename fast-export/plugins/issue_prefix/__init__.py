# encoding=UTF-8
"""__init__.py"""
import re

def build_filter(args):
    return Filter(args)

class Filter:
    def __init__(self, args):
        self.prefix = args.encode('utf8')

    def commit_message_filter(self, commit_data):
        for match in re.findall(b'#[1-9][0-9]+', commit_data['desc']):
            commit_data['desc'] = commit_data['desc'].replace(
                match, b'#%s%s' % (self.prefix, match[1:]))
