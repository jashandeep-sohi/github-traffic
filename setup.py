from setuptools import setup

setup(
    name="github_traffic",
    version="0.1.0",
    py_modules=["github_traffic"],
    entry_points="""
      [console_scripts]
      github-traffic=github_traffic:cli
    """
)
