#!/usr/bin/python
# encoding: utf-8
#
# Copyright © 2014 deanishe@deanishe.net
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2014-12-29
#

"""reddit.py [options] [args]

Usage:
    reddit.py <query>
    reddit.py --openurl <postdata>
    reddit.py --opencomments <postdata>

Options:
    -h, --help       Show this help text
    --openurl        Open the URL of the post in default browser
    --opencomments   Open the URL of Reddit post in default browser

"""

from __future__ import print_function, unicode_literals, absolute_import

from datetime import datetime
import json
import os
import re
import subprocess
import sys

from workflow import Workflow, web, ICON_WARNING

# How many posts to retrieve
POST_COUNT = 50

# How many subreddits to retrieve
SUBREDDIT_COUNT = 25

# How long to cache results for
CACHE_MAX_AGE = 180

# GitHub update settings
UPDATE_SETTINGS = {'github_slug': 'deanishe/alfred-reddit'}

HELP_URL = 'https://github.com/deanishe/alfred-reddit'


ICON_REDDIT = os.path.join(os.path.dirname(__file__), 'icon.png')
ICON_UPDATE = os.path.join(os.path.dirname(__file__), 'update-available.png')

POST_URL = 'http://www.reddit.com/r/{name}/hot.json'

SEARCH_URL = 'http://www.reddit.com/subreddits/search.json'

POPULAR_URL = 'http://www.reddit.com/subreddits/popular.json'

USER_AGENT = 'Alfred-Reddit/{version} ({url})'

log = None


def cache_key(name):
    """Make filesystem-friendly cache key"""
    key = name.lower()
    key = re.sub(r'[^a-z0-9-_\.]', '-', key)
    key = re.sub(r'-+', '-', key)
    log.debug('Cache key : {!r} -> {!r}'.format(name, key))
    return key


def relative_time(timestamp):
    """Return human-readable, relative time"""
    now = datetime.utcnow()
    postdate = datetime.utcfromtimestamp(timestamp)
    delta = now - postdate
    seconds = delta.seconds
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    # log.debug('Post is {!r} old'.format(delta))
    if days:
        return '{} day{} ago'.format(days, 's'[days == 1:])
    if hours:
        return '{} hr{} ago'.format(hours, 's'[hours == 1:])
    if minutes:
        return '{} min{} ago'.format(minutes, 's'[minutes == 1:])
    if seconds:
        return '{} sec{} ago'.format(seconds, 's'[seconds == 1:])
    else:
        return '1 sec ago'


def handle_post(api_dict):
    """Strip down API dict"""
    data = api_dict.get('data', {})
    post = {}
    for key in ('title', 'url', 'author'):
        post[key] = data[key]
    post['timestamp'] = data['created_utc']
    post['reltime'] = relative_time(data['created_utc'])
    post['permalink'] = 'http://www.reddit.com{}'.format(data['permalink'])
    return post


def handle_subreddit(api_dict):
    """Strip down API dict"""
    data = api_dict.get('data', {})
    sr = {}
    sr['name'] = data['display_name']
    sr['title'] = data['title']
    sr['type'] = data['subreddit_type']

    return sr


def popular_subreddits(limit=SUBREDDIT_COUNT):
    """Return list of popular subreddits"""
    log.debug('Fetching list of popular subreddits ...')

    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}

    params = {'limit': limit}

    r = web.get(POPULAR_URL, params, headers=headers)

    log.debug('[{}] {}'.format(r.status_code, r.url))

    r.raise_for_status()

    subreddits = r.json()['data']['children']
    # log.debug(pformat(subreddits))
    subreddits = [handle_subreddit(d) for d in subreddits]
    subreddits = [d for d in subreddits if d['type'] != 'private']

    for sr in subreddits:
        log.debug(sr)

    return subreddits


def search_subreddits(query, limit=SUBREDDIT_COUNT):
    """Return list of subreddits matching `query`"""
    log.debug('Searching for subreddits matching {!r} ...'.format(query))
    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}

    params = {'limit': limit, 'q': query}

    r = web.get(SEARCH_URL, params, headers=headers)
    log.debug('[{}] {}'.format(r.status_code, r.url))

    r.raise_for_status()

    subreddits = r.json()['data']['children']

    subreddits = [handle_subreddit(d) for d in subreddits]
    # Only show public subreddits
    subreddits = [d for d in subreddits if d['type'] == 'public']

    for sr in subreddits:
        log.debug(sr)

    return subreddits


def subreddit(name, limit=POST_COUNT):
    """Return list of hot posts on specified subreddit"""
    log.debug('Fetching hot posts in r/{} ...'.format(name))
    url = POST_URL.format(name=name)
    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}
    params = {'limit': limit}

    log.debug('url : {}'.format(url))
    r = web.get(url, params, headers=headers)
    log.debug('[{}] {}'.format(r.status_code, r.url))

    # API redirects to subreddit search instead of returning a 404 :(
    if r.status_code == 404 or r.url.startswith(SEARCH_URL):
        msg = 'Not a subreddit : `{}`'.format(name)
        log.error(msg)
        return None

    r.raise_for_status()

    data = r.json()
    posts = [handle_post(d) for d in data['data']['children']]

    return posts


def post_search_key(post):
    return '{} {}'.format(post['title'], post['author'])


def subreddit_search_key(sr):
    return '{} {}'.format(sr['name'], sr['title'])


def main(wf):

    from docopt import docopt
    args = docopt(__doc__, wf.args)

    log.debug('args : {!r}'.format(args))

    # Run Script actions
    # ------------------------------------------------------------------

    if args.get('<postdata>'):

        d = json.loads(args.get('<postdata>'))

        if args.get('--openurl'):
            url = d['url']
        elif args.get('--opencomments'):
            url = d['permalink']

        log.debug('Opening : {}'.format(url))
        subprocess.call(['open', url])

        return 0

    ####################################################################
    # Script Filter
    ####################################################################

    # Updates
    # ------------------------------------------------------------------

    if wf.update_available:
        wf.add_item('A newer version is available',
                    '↩ to install update',
                    autocomplete='workflow:update',
                    icon=ICON_UPDATE)

    query = args.get('<query>')

    log.debug('query : {!r}'.format(query))

    # Show popular subreddits
    # ------------------------------------------------------------------

    if query == '':

        subreddits = wf.cached_data('--popular', popular_subreddits,
                                    max_age=CACHE_MAX_AGE)

        for sr in subreddits:

            wf.add_item(sr['name'],
                        sr['title'],
                        autocomplete='{}/'.format(sr['name']),
                        icon=ICON_REDDIT)

        wf.send_feedback()
        return 0

    # Parse query
    # ------------------------------------------------------------------

    # r/blah -> Search for subreddit matching `blah`
    # r/blah/ -> List hot posts in r/blah
    # r/blah/wut -> Filter hot posts in r/blah by `wut`
    m = re.match('([^/]+)(/)?(.+)?', query)

    if not m:
        wf.add_item('Invalid query',
                    'Try a different query',
                    icon=ICON_WARNING)
        wf.send_feedback()
        return 0

    name, slash, query = m.groups()

    log.debug('name : {!r} slash : {!r}  query : {!r}'.format(
              name, slash, query))

    # Search for matching subreddit
    # ------------------------------------------------------------------

    if not slash:

        key = '--search-{}'.format(cache_key(name))

        subreddits = wf.cached_data(key, lambda: search_subreddits(name),
                                    max_age=CACHE_MAX_AGE)

        # Filter results because Reddit's search is super-crappy
        subreddits = wf.filter(name, subreddits,
                               key=subreddit_search_key,
                               min_score=30)

        if not subreddits:

            wf.add_item('No matching subreddits found',
                        'Try a different query',
                        icon=ICON_WARNING)

        else:  # List all matching subreddits

            for sr in subreddits:

                log.debug(repr(sr))

                # Encode arg to send to Run Script
                arg = json.dumps({
                    'name': sr['name'],
                    'title': sr['title'],
                    'url': 'http://www.reddit.com/r/{}'.format(sr['name'])})

                wf.add_item(sr['name'],
                            sr['title'],
                            autocomplete='{}/'.format(sr['name']),
                            arg=arg,
                            valid=True,
                            icon=ICON_REDDIT)

        wf.send_feedback()
        return 0

    # Browse/search within subreddit
    # ------------------------------------------------------------------

    # Filesystem-friendly key
    key = cache_key(name)

    log.debug('Viewing r/{} ...'.format(name))

    posts = wf.cached_data(key, lambda: subreddit(name), max_age=CACHE_MAX_AGE)

    if posts is None:  # Non-existent subreddit
        wf.add_item('r/{} does not exist'.format(name),
                    'Try a different name',
                    icon=ICON_WARNING)

        wf.send_feedback()
        return 0

    if query:
        posts = wf.filter(query, posts, key=post_search_key, min_score=30)

    if not posts:
        wf.add_item('No matching results found',
                    'Try a different subreddit and/or query',
                    icon=ICON_WARNING)

    for post in posts:
        subtitle = 'Posted {} by {} // {}'.format(post['reltime'],
                                                  post['author'],
                                                  post['url'])

        # Encode arg to send to Run Script
        arg = json.dumps({'url': post['url'], 'permalink': post['permalink']})

        modifiers = {}

        if post['url'] != post['permalink']:  # Not a Self post
            modifiers['cmd'] = 'View Comments on Reddit'
        else:
            modifiers['cmd'] = '[Self post] View on Reddit'

        wf.add_item(post['title'],
                    subtitle,
                    modifier_subtitles=modifiers,
                    arg=arg,
                    largetext=post['title'],
                    valid=True,
                    icon=ICON_REDDIT)

    wf.send_feedback()

    log.debug('{} hot posts in subreddit `{}`'.format(len(posts), name))


if __name__ == '__main__':
    wf = Workflow(help_url=HELP_URL,
                  update_settings=UPDATE_SETTINGS)
    log = wf.logger
    sys.exit(wf.run(main))
