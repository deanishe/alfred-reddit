#!/usr/bin/python
# encoding: utf-8
#
# Copyright © 2014 deanishe@deanishe.net
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2014-12-29
#

"""reddit.py [options] <query>

Browse and search subreddits and hot posts.

Usage:
    reddit.py <query>
    reddit.py [-c] [-p] [-s]

Options:
    -c, --comments        Open Reddit comments page in browser
    -p, --post            Open post in browser
    -s, --subreddit       Open subreddit in browser
    -h, --help            Show this help text

"""

from __future__ import print_function, unicode_literals, absolute_import

from datetime import datetime
from functools import partial
import os
import re
import subprocess
import sys

from workflow import Workflow3, web, ICON_WARNING


# dP     dP                   oo          dP       dP
# 88     88                               88       88
# 88    .8P .d8888b. 88d888b. dP .d8888b. 88d888b. 88 .d8888b. .d8888b.
# 88    d8' 88'  `88 88'  `88 88 88'  `88 88'  `88 88 88ooood8 Y8ooooo.
# 88  .d8P  88.  .88 88       88 88.  .88 88.  .88 88 88.  ...       88
# 888888'   `88888P8 dP       dP `88888P8 88Y8888' dP `88888P' `88888P'

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

# JSON list of hot posts in subreddit
HOT_POSTS_URL = 'https://www.reddit.com/r/{name}/hot.json'

# JSON subreddit search
SEARCH_URL = 'https://www.reddit.com/subreddits/search.json'

# JSON list of popular subreddits
POPULAR_URL = 'https://www.reddit.com/subreddits/popular.json'

# HTML URL of subreddit
SUBREDDIT_URL = 'https://www.reddit.com/r/{display_name}/'

# HTML URL of post
POST_URL = 'https://www.reddit.com{permalink}'

USER_AGENT = 'Alfred-Reddit/{version} ({url})'

# Populated on run
log = None


# dP     dP           dP
# 88     88           88
# 88aaaaa88a .d8888b. 88 88d888b. .d8888b. 88d888b. .d8888b.
# 88     88  88ooood8 88 88'  `88 88ooood8 88'  `88 Y8ooooo.
# 88     88  88.  ... 88 88.  .88 88.  ... 88             88
# dP     dP  `88888P' dP 88Y888P' `88888P' dP       `88888P'
#                        88
#                        dP

def open_url(url):
    """Open URL in default browser."""
    log.debug('Opening : %s', url)
    subprocess.call(['open', url])


def cache_key(name):
    """Make filesystem-friendly cache key."""
    key = name.lower()
    key = re.sub(r'[^a-z0-9-_\.]', '-', key)
    key = re.sub(r'-+', '-', key)
    log.debug('Cache key : {!r} -> {!r}'.format(name, key))
    return key


def relative_time(timestamp):
    """Return human-readable, relative time."""
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


#  888888ba                 dP       dP oo   dP       .d888888   888888ba  dP
#  88    `8b                88       88      88      d8'    88   88    `8b 88
# a88aaaa8P' .d8888b. .d888b88 .d888b88 dP d8888P    88aaaaa88a a88aaaa8P' 88
#  88   `8b. 88ooood8 88'  `88 88'  `88 88   88      88     88   88        88
#  88     88 88.  ... 88.  .88 88.  .88 88   88      88     88   88        88
#  dP     dP `88888P' `88888P8 `88888P8 dP   dP      88     88   dP        dP

def parse_post(api_dict):
    """Strip down API dict."""
    d = api_dict.get('data', {})
    post = {
        'title': d['title'],
        'post_url': d['url'],
        'author': d['author'],
        'timestamp': d['created_utc'],
        'reltime': relative_time(d['created_utc']),
        'comments_url': POST_URL.format(**d)
    }
    post['selfpost'] = post['post_url'] == post['comments_url']
    return post


def parse_subreddit(api_dict):
    """Strip down API dict."""
    d = api_dict.get('data', {})
    return {
        'name': d['display_name'],
        'title': d['title'],
        'type': d['subreddit_type'],
        'url': SUBREDDIT_URL.format(**d),
    }


def popular_subreddits(limit=SUBREDDIT_COUNT):
    """Return list of popular subreddits."""
    log.debug('Fetching list of popular subreddits ...')

    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}

    params = {'limit': limit}

    r = web.get(POPULAR_URL, params, headers=headers)

    log.debug('[%d] %s', r.status_code, r.url)

    r.raise_for_status()

    subreddits = r.json()['data']['children']
    # log.debug(pformat(subreddits))
    subreddits = [parse_subreddit(d) for d in subreddits]
    subreddits = [d for d in subreddits if d['type'] != 'private']

    for sr in subreddits:
        log.debug(sr)

    return subreddits


def search_subreddits(query, limit=SUBREDDIT_COUNT):
    """Return list of subreddits matching `query`."""
    log.debug('Searching for subreddits matching %r ...', query)
    headers = {
        'user-agent': USER_AGENT.format(version=wf.version,
                                        url=wf.help_url)
    }

    params = {'limit': limit, 'q': query}

    r = web.get(SEARCH_URL, params, headers=headers)
    log.debug('[%d] %s', r.status_code, r.url)

    r.raise_for_status()

    subreddits = r.json()['data']['children']

    subreddits = [parse_subreddit(d) for d in subreddits]
    # Only show public subreddits
    subreddits = [d for d in subreddits if d['type'] == 'public']

    for sr in subreddits:
        log.debug(sr)

    return subreddits


def hot_posts(name, limit=POST_COUNT):
    """Return list of hot posts on specified subreddit."""
    log.debug('Fetching hot posts in r/%s ...', name)
    url = HOT_POSTS_URL.format(name=name)
    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}
    params = {'limit': limit}

    log.debug('url : %s', url)
    r = web.get(url, params, headers=headers)
    log.debug('[%d] %s', r.status_code, r.url)

    # API redirects to subreddit search instead of returning a 404 :(
    if r.status_code == 404 or r.url.startswith(SEARCH_URL):
        msg = 'Not a subreddit : `{}`'.format(name)
        log.error(msg)
        return None

    r.raise_for_status()

    data = r.json()
    posts = [parse_post(d) for d in data['data']['children']]

    return posts


def post_search_key(post):
    """Search key for post."""
    return '{} {}'.format(post['title'], post['author'])


def subreddit_search_key(sr):
    """Search key for subreddit."""
    return '{} {}'.format(sr['name'], sr['title'])


# dP   dP   dP                   dP       .8888b dP
# 88   88   88                   88       88   " 88
# 88  .8P  .8P .d8888b. 88d888b. 88  .dP  88aaa  88 .d8888b. dP  dP  dP
# 88  d8'  d8' 88'  `88 88'  `88 88888"   88     88 88'  `88 88  88  88
# 88.d8P8.d8P  88.  .88 88       88  `8b. 88     88 88.  .88 88.88b.88'
# 8888' Y88'   `88888P' dP       dP   `YP dP     dP `88888P' 8888P Y8P

def show_popular():
    """List popular subreddits."""
    subreddits = wf.cached_data('--popular', popular_subreddits,
                                max_age=CACHE_MAX_AGE)

    for sr in subreddits:
        url = sr['url']
        it = wf.add_item(sr['name'],
                         sr['title'],
                         autocomplete='{}/'.format(sr['name']),
                         quicklookurl=url,
                         icon=ICON_REDDIT)

        it.setvar('subreddit_url', url)
        it.add_modifier('cmd',
                        'View "r/{}" in browser'.format(sr['name']),
                        valid=True).setvar('argv', '-s')

    wf.send_feedback()
    return 0


def show_search(name):
    """List subreddits matching `name`."""
    key = '--search-{}'.format(cache_key(name))

    subreddits = wf.cached_data(key,
                                partial(search_subreddits, name),
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

            url = sr['url']
            it = wf.add_item(sr['name'],
                             sr['title'],
                             autocomplete='{}/'.format(sr['name']),
                             arg=url,
                             uid=sr['name'],
                             quicklookurl=url,
                             valid=True,
                             icon=ICON_REDDIT)

            it.setvar('subreddit_url', url)
            it.setvar('argv', '-s')

    wf.send_feedback()
    return 0


def show_posts(name, query):
    """List posts within subreddit `name`."""
    # Whether Quick Look shows post or comments
    qlpost = os.getenv('QUICKLOOK_POST') == "1"

    # Filesystem-friendly key
    key = cache_key(name)

    log.debug('Viewing r/%s ...', name)

    posts = wf.cached_data(key,
                           partial(hot_posts, name),
                           max_age=CACHE_MAX_AGE)

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
                                                  post['post_url'])

        if qlpost:
            qlurl = post['post_url']
        else:
            qlurl = post['comments_url']

        it = wf.add_item(post['title'],
                         subtitle,
                         arg=post['post_url'],
                         largetext=post['title'],
                         valid=True,
                         quicklookurl=qlurl,
                         icon=ICON_REDDIT)

        it.setvar('post_url', post['post_url'])
        it.setvar('comments_url', post['comments_url'])
        it.setvar('argv', '-p')

        csub = 'View comments on Reddit'
        cargv = '-c'
        asub = 'View both article and comments in browser'
        aargv = '-c -p'

        if post['selfpost']:
            csub = asub = '[Self post] View on Reddit'
            aargv = '-c'

        it.add_modifier('cmd', csub, valid=True).setvar('argv', cargv)
        it.add_modifier('alt', asub, valid=True).setvar('argv', aargv)

    wf.send_feedback()

    log.debug('%d hot posts in subreddit `%s`', posts, name)


def main(wf):
    """Run workflow."""
    from docopt import docopt
    args = docopt(__doc__, wf.args)

    log.debug('args : %r', args)

    # Run Script actions
    # ------------------------------------------------------------------

    done = False
    if args.get('--post'):
        open_url(os.getenv('post_url'))
        done = True

    if args.get('--comments'):
        open_url(os.getenv('comments_url'))
        done = True

    if args.get('--subreddit'):
        open_url(os.getenv('subreddit_url'))
        done = True

    if done:
        return

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
    log.debug('query : %r', query)

    # Show popular subreddits
    # ------------------------------------------------------------------
    if query == '':
        return show_popular()

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

    log.debug('name : %r slash : %r  query : %r', name, slash, query)

    # Search for matching subreddit
    # ------------------------------------------------------------------
    if not slash:
        return show_search(name)

    # Browse/search within subreddit
    # ------------------------------------------------------------------
    return show_posts(name, query)


if __name__ == '__main__':
    wf = Workflow3(help_url=HELP_URL,
                   update_settings=UPDATE_SETTINGS)
    log = wf.logger
    sys.exit(wf.run(main))
