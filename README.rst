--------------
github-traffic
--------------

Summarize Github traffic stats across repos


Requirements
------------

- Python 3

Install
-------

To install the latest development version::

  $ pip install --user git+https://github.com/jashandeep-sohi/github-traffic.git

Usage
-----

Views & clones summary::

  $ github-traffic --token "$GITHUB_TOKEN" summary

Views summary::

  $ github-traffic --token "$GITHUB_TOKEN" summary --metrics views

Clones summary::

  $ github-traffic --token "$GITHUB_TOKEN" summary --metrics clones

Top referrers::

  $ github-traffic --token "$GITHUB_TOKEN" referrers

Top paths::

  $ github-traffic --token "$GITHUB_TOKEN" paths
