#!/usr/bin/python
# encoding: utf-8
#
# Copyright (c) 2014 deanishe@deanishe.net
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2014-12-29
#

"""reddit.py [options] <query>

Browse and search subreddits and hot posts.

Usage:
    reddit.py <query>
    reddit.py --search <query>
    reddit.py --update
    reddit.py [-c] [-p] [-s] [-b]

Options:
    -c, --comments        Open Reddit comments page in browser
    -p, --post            Open post in browser
    -s, --subreddit       Open subreddit in browser
    -b, --submit          Submit link/text to subreddit
    --search <query>      Search for subreddits using API
    -u, --update          Update list of top subreddits
    -h, --help            Show this help text

"""

from __future__ import print_function, unicode_literals, absolute_import

from datetime import datetime
from HTMLParser import HTMLParser
from functools import partial
import os
import re
import subprocess
import sys

from workflow import Workflow3, web, ICON_WARNING
from workflow.background import is_running, run_in_background


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

# How long to cache searches for subreddits for
SEARCH_CACHE_MAX_AGE = 3600  # 1 hour

# How long to cache lists of posts for
POSTS_CACHE_MAX_AGE = 180  # 3 minutes

# How long to cache list of top subreddits
TOP_CACHE_MAX_AGE = 86400  # 1 day

# How many top reddits to cache
TOP_COUNT = 500

# Include NSFW subreddits
NSFW = os.getenv('NSFW', '0').lower() in ('1', 'true', 'yes', 'on')

# GitHub update settings
UPDATE_SETTINGS = {'github_slug': 'deanishe/alfred-reddit'}

HELP_URL = 'https://github.com/deanishe/alfred-reddit'


ICON_REDDIT = 'icon.png'
ICON_UPDATE = 'update-available.png'

# JSON list of hot posts in subreddit
HOT_POSTS_URL = 'https://www.reddit.com/r/{name}/hot.json'
# HOT_POSTS_URL = 'https://www.reddit.com/{name}/hot.json'

# JSON list of hot posts in user multi
USER_MULTI_HOT_URL = 'https://www.reddit.com/{name}.json'

# JSON subreddit search
SEARCH_URL = 'https://www.reddit.com/subreddits/search.json'

# JSON list of popular subreddits
POPULAR_URL = 'https://www.reddit.com/subreddits/popular.json'

# HTML URL of subreddit
SUBREDDIT_URL = 'https://www.reddit.com/r/{name}/'

# HTML URL of user multi
USER_MULTI_URL = 'https://www.reddit.com/{name}/'

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
    log.debug('Cache key : %r -> %r', name, key)
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


def decode_html_entities(s):
    """Decode HTML entities into Unicode."""
    h = HTMLParser()
    return h.unescape(s)


def subreddit_from_env():
    """Return subreddit based on env vars."""
    sr = dict(
        name=os.getenv('subreddit_name'),
        title=os.getenv('subreddit_title'),
        type=os.getenv('subreddit_type'),
        url=os.getenv('subreddit_url')
    )
    if None in sr.values():
        return None

    log.debug('subreddit from env=%r', sr)
    return sr


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
        'title': decode_html_entities(d['title']),
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
        'title': decode_html_entities(d['title']),
        'type': d['subreddit_type'],
        'url': subreddit_url(d['display_name']),
    }


def popular_subreddits(limit=SUBREDDIT_COUNT, after=None):
    """Return list of popular subreddits."""
    log.debug('Fetching list of popular subreddits ...')

    headers = {'user-agent': USER_AGENT.format(version=wf.version,
                                               url=wf.help_url)}

    params = {'limit': limit}
    if after:
        params['after'] = after

    r = web.get(POPULAR_URL, params, headers=headers)

    log.debug('[%d] %s', r.status_code, r.url)

    r.raise_for_status()

    data = r.json()['data']
    after = data['after']
    subreddits = data['children']

    subreddits = [parse_subreddit(d) for d in subreddits]
    subreddits = [d for d in subreddits if d['type'] != 'private']

    return subreddits, after


def search_subreddits(query, limit=SUBREDDIT_COUNT, nsfw=NSFW):
    """Return list of subreddits matching ``query``."""
    log.debug('Searching for subreddits matching %r ...', query)
    headers = {
        'user-agent': USER_AGENT.format(version=wf.version,
                                        url=wf.help_url)
    }

    nsfw = 1 if NSFW else 0
    params = {'limit': limit, 'q': query, 'include_over_18': nsfw}

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
    url = hot_url(name)
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
    return sr['name']
    # return '{} {}'.format(sr['name'], sr['title'])


def subreddit_url(name):
    """Make URL for subreddit."""
    if name.startswith('u/'):  # user multi
        return USER_MULTI_URL.format(name=name)
    return SUBREDDIT_URL.format(name=name)


def hot_url(name):
    """Make URL for hot posts."""
    if name.startswith('u/'):  # user multi
        return USER_MULTI_HOT_URL.format(name=name)
    return HOT_POSTS_URL.format(name=name)


# dP   dP   dP                   dP       .8888b dP
# 88   88   88                   88       88   " 88
# 88  .8P  .8P .d8888b. 88d888b. 88  .dP  88aaa  88 .d8888b. dP  dP  dP
# 88  d8'  d8' 88'  `88 88'  `88 88888"   88     88 88'  `88 88  88  88
# 88.d8P8.d8P  88.  .88 88       88  `8b. 88     88 88.  .88 88.88b.88'
# 8888' Y88'   `88888P' dP       dP   `YP dP     dP `88888P' 8888P Y8P

def clear_cache():
    """Remove old cache files."""
    def okay(fn):
        if not fn.startswith('--') or not fn.endswith('.cpickle'):
            return False

        n, _ = os.path.splitext(fn)
        if not wf.cached_data_fresh(n, TOP_CACHE_MAX_AGE):
            return True

        return False

    wf.clear_cache(okay)
    wf.clear_session_cache()


def update_top_subreddits():
    """Update the cached list of popular subreddits."""
    after = None
    subreddits = []

    while len(subreddits) < TOP_COUNT:
        res, after = popular_subreddits(100, after)
        subreddits.extend(res)

    wf.cache_data('__top', subreddits)


def remember_subreddit(name=None):
    """Add current subreddit to history."""
    if name:
        last = wf.cached_data('--last', max_age=0, session=True) or {}
        sr = last.get(name)
        if not sr:  # must be a multi
            sr = dict(name=name, title=name, type="public",
                      url=subreddit_url(name))
    else:
        sr = subreddit_from_env()

    if not sr:
        log.debug('no subreddit to save to history')
        return

    subreddits = wf.cached_data('__history', max_age=0) or []
    log.debug('%d subreddit(s) in history', len(subreddits))
    for d in subreddits:
        if sr['name'].lower() == d['name'].lower():
            log.debug('%r already in history', sr['name'])
            return

    subreddits.append(sr)
    wf.cache_data('__history', subreddits)
    log.debug('added %r to history', sr['name'])
    log.debug('%d subreddit(s) in history', len(subreddits))


def parse_query(query):
    """Parse ``query`` into ``name``, ``slash``, ``query``.

    Args:
        query (unicode): User query

    Returns:
        tuple: ``name``, ``slash``, ``query``.

    """
    # r/blah -> Search for subreddit matching `blah`
    # r/blah/ -> List hot posts in r/blah
    # r/blah/wut -> Filter hot posts in r/blah by `wut`
    m = re.match(r'(u/\w+/m/[^/]+)(/)(.+)?', query)  # user multi
    if not m:
        m = re.match(r'([^/]+)(/)?(.+)?', query)  # normal subreddit

    if not m:
        return None, None, None

    name, slash, query = m.groups()

    log.debug('name : %r slash : %r  query : %r', name, slash, query)
    return name, slash, query


def show_top():
    """List history and top subreddits."""
    subreddits = wf.cached_data('__history', max_age=0) or []
    top = wf.cached_data('__top', max_age=0) or []
    seen = {sr['name'] for sr in subreddits}
    for sr in top:
        if sr['name'] not in seen:
            subreddits.append(sr)

    if len(subreddits) > 200:
        subreddits = subreddits[:200]

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
        it.add_modifier('alt',
                        'Make post in "r/{}" in browser'.format(sr['name']),
                        valid=True).setvar('argv', '-b')

    if is_running('top'):
        wf.rerun = 0.2

    wf.send_feedback()
    return 0


def show_search(name, nsfw=NSFW):
    """List subreddits matching `name`."""
    nsfw = 'nsfw-' if nsfw else ''
    top = wf.cached_data('__top', max_age=0) or []
    history = wf.cached_data('__history', max_age=0) or []
    key = '--search-{}{}'.format(nsfw, cache_key(name))

    # Load cached results for name or start search in background
    cached = wf.cached_data(key, None, SEARCH_CACHE_MAX_AGE) or []
    if not cached and not is_running('search'):
        run_in_background('search', ['/usr/bin/python', 'reddit.py',
                          '--search', name.encode('utf-8')])
        wf.rerun = 0.3

    log.debug('loaded subreddits: %d history, %d top, %d cached',
              len(history), len(top), len(cached))

    if is_running('search'):
        wf.rerun = 0.3

    subreddits = history
    other = top + cached
    seen = {sr['name'] for sr in history}
    for sr in other:
        if sr['name'] in seen:
            continue
        subreddits.append(sr)
        seen.add(sr['name'])

    # Filter results because Reddit's search is super-crappy
    subreddits = wf.filter(name, subreddits,
                           key=lambda sr: sr['name'],
                           min_score=30)

    if not subreddits:
        if is_running('search'):
            wf.add_item('Loading from API …',
                        'Hang in there')
        else:
            wf.add_item('No matching subreddits found',
                        'Try a different query',
                        icon=ICON_WARNING)
        wf.send_feedback()
        return

    # Cache all subreddits in case we need to "remember" one
    results = {sr['name']: sr for sr in subreddits}
    wf.cache_data('--last', results, session=True)

    # List all matching subreddits

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

        # Export subreddit to ENV in case we want to save it
        it.setvar('subreddit_name', sr['name'])
        it.setvar('subreddit_title', sr['title'])
        it.setvar('subreddit_type', sr['type'])
        it.setvar('subreddit_url', url)
        it.setvar('argv', '-s')
        it.add_modifier('alt',
                        'Make post in "r/{}" in browser'.format(sr['name']),
                        valid=True).setvar('argv', '-b')

    wf.send_feedback()
    return


def show_posts(name, query):
    """List posts within subreddit `name`."""
    # Whether Quick Look shows post or comments
    qlpost = os.getenv('QUICKLOOK_POST') == "1"

    # Filesystem-friendly key
    key = '--subreddit-' + cache_key(name)

    log.debug('Viewing r/%s ...', name)

    posts = wf.cached_data(key,
                           partial(hot_posts, name),
                           max_age=POSTS_CACHE_MAX_AGE)

    if posts is None:  # Non-existent subreddit
        wf.add_item('r/{} does not exist'.format(name),
                    'Try a different name',
                    icon=ICON_WARNING)

        wf.send_feedback()
        return 0

    # Add to history
    remember_subreddit(name)

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

    log.debug('%d hot posts in subreddit `%s`', len(posts), name)


def main(wf):
    """Run workflow."""
    from docopt import docopt
    args = docopt(__doc__, wf.args)

    log.debug('args : %r', args)

    # Run Script actions
    # ------------------------------------------------------------------

    if args.get('--post'):
        open_url(os.getenv('post_url'))
        return

    if args.get('--comments'):
        open_url(os.getenv('comments_url'))
        return

    if args.get('--subreddit'):
        remember_subreddit()
        open_url(os.getenv('subreddit_url'))
        return

    if args.get('--submit'):
        open_url(os.getenv('subreddit_url') + 'submit')
        return

    ####################################################################
    # Background tasks
    ####################################################################

    # Update cached list of top subreddits
    if args.get('--update'):
        log.info('updating list of top subreddits ...')
        update_top_subreddits()
        log.info('updated list of top subreddits.')
        return

    # Search using API and cache results
    if args.get('--search'):
        name = wf.decode(args.get('--search'))
        nsfw = 'nsfw-' if NSFW else ''
        key = '--search-{}{}'.format(nsfw, cache_key(name))
        log.info('searching API for %r ...', name)
        subreddits = search_subreddits(name)
        wf.cache_data(key, subreddits)
        log.info('API returned %d subreddit(s) for %r', len(subreddits), name)
        # Tidy up cache in a background task to keep things snappy
        clear_cache()
        return

    # Update cached list of top subreddits
    if not is_running('top') and \
            not wf.cached_data_fresh('__top', TOP_CACHE_MAX_AGE):
        run_in_background('top', ['/usr/bin/python', 'reddit.py', '--update'])

    ####################################################################
    # Script Filter
    ####################################################################

    # Workflow updates
    # ------------------------------------------------------------------
    if wf.update_available:
        wf.add_item('A newer version is available',
                    '↩ to install update',
                    autocomplete='workflow:update',
                    icon=ICON_UPDATE)

    # Show popular subreddits
    # ------------------------------------------------------------------
    query = args.get('<query>')
    log.debug('query=%r', query)

    if query == '':
        return show_top()

    # Show subreddit or posts
    # ------------------------------------------------------------------

    name, slash, query = parse_query(query)
    if not name:
        wf.add_item('Invalid query',
                    'Try a different query',
                    icon=ICON_WARNING)
        wf.send_feedback()
        return 0

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
