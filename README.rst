|pypi-badge|

github-traffic
==============

Summarize Github traffic stats across repos


Install
-------

Latest stable::

  $ pip install --user github-traffic

Latest pre-release::

  $ pip install --user --pre github-traffic

Git::

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

.. |pypi-badge| image:: https://img.shields.io/pypi/v/github-traffic
    :alt: PyPI
    :target: https://pypi.org/project/github-traffic/
