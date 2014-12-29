
# Reddit for Alfred #

Find subreddits and browse hot posts on [Reddit][reddit].

![][demo]

## Download ##

Get Reddit for Alfred from [GitHub][gh-releases] or [Packal][packal-page].

## Usage ##

- `r/` — Show list of popular subreddits
- `r/<query>` — Search for subreddits matching `<query>`
    - `↩` or `⇥` or `⌘+NUM` — Show 50 hottest posts in subreddit
- `r/subreddit/` — Show 50 hottest posts on subreddit `<subreddit>`
- `r/<subreddit>/<query>` — Filter posts by `<query>`
    - `↩` or `⌘+NUM` — Open post URL in default browser
    - `⌘+↩` — Open Reddit comments in default browser
    - `⌘+L` — Show full post title in Alfred's Large Text window

**Note:** OS X's "delete word" shortcut (`⌥+⌫`) is very handy for backing
out of a subreddit.

## Description ##

A fairly rudimentary workflow to browse subreddits.

The subreddit search, `r/<query>`, uses Reddit's API to search for subreddits
that match `<query>`. 25 results are retrieved by default.

The subreddit search can be a bit odd, which is due to the oddness of Reddit's
search function.

Search within a subreddit, `r/subreddit/<query>`, only filters the list of hot
results. 50 results are retrieved by default.

## Licensing, thanks etc. ##

Alfred-Reddit is released under the [MIT Licence][mit].

I found the logo in a [Font Awesome issue][logo-source] on GitHub.

It's heavily based on [Alfred-Workflow][alfred-workflow], also [MIT-licensed][mit].

[reddit]: http://www.reddit.com
[mit]: http://opensource.org/licenses/MIT
[alfred-workflow]: http://www.deanishe.net/alfred-workflow/
[logo-source]: https://github.com/FortAwesome/Font-Awesome/issues/372
[gh-releases]: https://github.com/deanishe/alfred-reddit/releases
[packal-page]: http://www.packal.org/workflow/reddit
[demo]: https://raw.githubusercontent.com/deanishe/alfred-reddit/master/demo.gif
