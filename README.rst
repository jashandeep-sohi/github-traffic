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

  $ pip install git+https://github.com/jashandeep-sohi/github-traffic.git

Usage
-----

Views & clones breakdown::

  $ github-traffic --token "$GITHUB_TOKEN" breakdown

Views breakdown::

  $ github-traffic --token "$GITHUB_TOKEN" breakdown --metrics views

Clones breakdown::

  $ github-traffic --token "$GITHUB_TOKEN" breakdown --metrics clones

Top referrers::

  $ github-traffic --token "$GITHUB_TOKEN" referrers

Top paths::

  $ github-traffic --token "$GITHUB_TOKEN" paths
