import datetime
import logging
import json
import concurrent.futures
import time

import click
import github

from concurrent.futures import ThreadPoolExecutor

from github import Github
from terminaltables import AsciiTable
from click_aliases import ClickAliasedGroup


logger = logging.getLogger(__name__)


@click.group(cls=ClickAliasedGroup)
@click.option("--token", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--ignore",
  default="",
  help="comma seperated list of repos to ignore"
)
@click.option("--include",
  default="",
  help="comma seperated list of repos to exclusively include"
)
@click.option(
    "--output-format",
    default="table",
    type=click.Choice(["table", "json"])
)
@click.option(
    "--order",
    default="asc",
    type=click.Choice(["desc", "asc"])
)
@click.option(
    "--parallel",
    default=10,
    type=click.IntRange(1, 100)
)
@click.pass_context
def cli(ctx, token, user, password, ignore, include, output_format, order,
        parallel):
    ctx.ensure_object(dict)

    ctx.obj["output_format"] = output_format
    ctx.obj["order"] = order
    ctx.obj["parallel_workers"] = parallel

    if token:
        g = Github(token)
    else:
        g = Github(user, password)

    repos = get_repos(g)

    ignore_repo_names = {x.strip() for x in ignore.split(",") if x.strip()}
    include_repo_names = {x.strip() for x in include.split(",") if x.strip()}

    ctx.obj["github"] = g
    ctx.obj["repos"] = list(
      x for x in filter_traffic_visible(repos)
      if x.name not in ignore_repo_names
    )

    if include_repo_names:
      ctx.obj["repos"] = list(
        x for x in ctx.obj["repos"]
        if x.name in include_repo_names
      )


@cli.command()
@click.option(
    "--metrics",
    default=["views", "clones"],
    type=click.Choice(["views", "clones"]),
    multiple=True
)
@click.option("--days", default=15, type=click.IntRange(0, 15))
@click.pass_context
def summary(ctx, metrics, days):
    repos = ctx.obj.get("repos")
    output_format = ctx.obj.get("output_format")
    order = ctx.obj.get("order")
    parallel_workers = ctx.obj.get("parallel_workers")

    metrics = set(metrics)

    show_views = "views" in metrics
    show_clones = "clones" in metrics

    today = datetime.datetime.utcnow().date()

    dates = list(reversed(list(
        date_days_range(today - datetime.timedelta(days=days-1), today)
    )))

    fake_traffic = list(get_repos_zero_traffic(repos, dates))

    if show_views:
        repos_views = list(get_repos_views_traffic(repos, dates, parallel_workers))

    else:
        repos_views = fake_traffic

    if show_clones:
        repos_clones = list(get_repos_clones_traffic(repos, dates, parallel_workers))
    else:
        repos_clones = fake_traffic

    repos_views = sorted(repos_views, key=lambda r: r["name"])
    repos_clones = sorted(repos_clones, key=lambda r: r["name"])

    if output_format == "json":
        out = {
            "views":  repos_views if show_views else None,
            "clones": repos_clones if show_clones else None
        }
        click.echo(json.dumps(out, default=str, indent=4, sort_keys=True))
    elif output_format == "table":
        table = build_summary_table(
            dates,
            repos_views,
            repos_clones,
            show_views,
            show_clones,
            True if order == "desc" else False
        )
        click.secho(table)


@cli.command(aliases=["refs", "hosts"])
@click.pass_context
def referrers(ctx):
    repos = ctx.obj.get("repos")
    output_format = ctx.obj.get("output_format")
    order = ctx.obj.get("order")
    parallel_workers = ctx.obj.get("parallel_workers")

    prog = progressbar(
        length=len(repos),
        show_eta=False,
        label="Fetching referrers stats",
        item_show_func=lambda r: r and r.name
    )
    with prog, ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        def get(repo):
            try:
                resp = repo.get_top_referrers()
            except github.RateLimitExceededException as e:
                retry_after = int(e.headers.get("retry-after", 0))
                if retry_after:
                    time.sleep(retry_after)
                    resp = repo.get_top_referrers()
                else:
                    raise e

            return resp, repo

        futures = (executor.submit(get, repo) for repo in repos)

        referrers = []
        for f in concurrent.futures.as_completed(futures):
            top_refs, repo = f.result()
            prog.update(1, repo)
            for r in top_refs:
                referrers.append(
                    {
                        "repo": repo.name,
                        "referrer": r.referrer,
                        "count": r.count,
                        "uniques": r.uniques
                    }
                )

    referrers = sorted(
      referrers,
      key=lambda x: (x["uniques"], x["count"], x["repo"]),
      reverse= True if order == "desc" else False
    )

    if output_format == "json":
        click.echo(json.dumps(referrers, indent=4, sort_keys=True))
    elif output_format == "table":
        labels = [["Repo", "Referrer", "Uniques", "Count"]]

        rows = []
        for ref in referrers:
            rows.append([
                ref["repo"], ref["referrer"], ref["uniques"], ref["count"]
            ])

        table_rows = labels + rows + labels

        table = AsciiTable(table_rows, "Referrers")
        table.inner_footing_row_border = True

        click.secho(table.table)


@cli.command()
@click.pass_context
def paths(ctx):
    repos = ctx.obj.get("repos")
    output_format = ctx.obj.get("output_format")
    order = ctx.obj.get("order")
    parallel_workers = ctx.obj.get("parallel_workers")

    prog = progressbar(
        length=len(repos),
        show_eta=False,
        label="Fetching paths stats",
        item_show_func=lambda r: r and r.name
    )
    with prog, ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        def get(repo):
            try:
                resp = repo.get_top_paths()
            except github.RateLimitExceededException as e:
                retry_after = int(e.headers.get("retry-after", 0))
                if retry_after:
                    time.sleep(retry_after)
                    resp = repo.get_top_paths()
                else:
                    raise e

            return resp, repo

        futures = (executor.submit(get, repo) for repo in repos)

        paths = []
        for f in concurrent.futures.as_completed(futures):
            top_paths, repo  = f.result()
            prog.update(1, repo)
            for p in top_paths:
                paths.append(
                    {
                        "repo": repo.name,
                        "path": p.path,
                        "title": p.title,
                        "count": p.count,
                        "uniques": p.uniques
                    }
                )

    paths = sorted(
      paths,
      key=lambda x: (x["uniques"], x["count"], x["repo"]),
      reverse= True if order == "desc" else False
    )

    if output_format == "json":
        click.echo(json.dumps(paths, indent=4, sort_keys=True))
    elif output_format == "table":
        labels = [["Repo", "Path", "Uniques", "Count"]]

        rows = []
        for path in paths:
            rows.append([
                path["repo"], path["path"], path["uniques"], path["count"]
            ])

        table_rows = labels + rows + labels

        table = AsciiTable(table_rows, "Paths")
        table.inner_footing_row_border = True

        click.secho(table.table)


def progressbar(*args, **kwargs):
    stderr_fobj = click.get_text_stream("stderr")

    return click.progressbar(*args, file=stderr_fobj, **kwargs)


def get_repos(g):
  try:
      repos = list(g.get_user().get_repos())
  except github.RateLimitExceededException as e:
      retry_after = int(e.headers.get("retry-after", 0))
      if retry_after:
          time.sleep(retry_after)
          repos = list(g.get_user().get_repos())
      else:
          raise e
  return repos

def filter_traffic_visible(repos):
    for repo in repos:
        if repo.permissions.push or repo.permissions.admin:
            yield repo


def date_days_range(start, end):
    days = (end - start).days

    for n in range(days + 1):
        yield start + datetime.timedelta(days=n)


def traffic_on_dates(traffic, dates):
    traffic_by_date = {t.timestamp.date(): t for t in traffic}

    for date in dates:
        if date in traffic_by_date:
            date_traffic = traffic_by_date[date]
            yield {
                "date": date,
                "uniques": date_traffic.uniques,
                "count": date_traffic.count
            }
        else:
            yield {
                "date": date,
                "uniques": 0,
                "count": 0
            }


def get_repos_views_traffic(repos, breakdown_dates, parallel_workers):
    prog = progressbar(
        length=len(repos),
        show_eta=False,
        label="Fetching views stats",
        item_show_func=lambda r: r and r.name
    )
    with prog, ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        def get(repo):
            try:
                resp = repo.get_views_traffic()
            except github.RateLimitExceededException as e:
                retry_after = int(e.headers.get("retry-after", 0))
                if retry_after:
                    time.sleep(retry_after)
                    resp = repo.get_views_traffic()
                else:
                    raise e

            return resp, repo

        futures = (executor.submit(get, repo) for repo in repos)

        for f in concurrent.futures.as_completed(futures):
            traffic, repo = f.result()
            prog.update(1, repo)
            breakdown = list(traffic_on_dates(traffic["views"], breakdown_dates))
            yield {
                "name": repo.name,
                "uniques": traffic["uniques"],
                "count": traffic["count"],
                "breakdown": breakdown
            }


def get_repos_clones_traffic(repos, breakdown_dates, parallel_workers):
    prog = progressbar(
        length=len(repos),
        show_eta=False,
        label="Fetching clones stats",
        item_show_func=lambda r: r and r.name
    )
    with prog, ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        def get(repo):
            try:
                resp = repo.get_clones_traffic()
            except github.RateLimitExceededException as e:
                retry_after = int(e.headers.get("retry-after", 0))
                if retry_after:
                    time.sleep(retry_after)
                    resp = repo.get_clones_traffic()
                else:
                    raise e

            return resp, repo

        futures = (executor.submit(get, repo) for repo in repos)

        for f in concurrent.futures.as_completed(futures):
            traffic, repo = f.result()
            prog.update(1, repo)
            breakdown = list(traffic_on_dates(traffic["clones"], breakdown_dates))
            yield {
                "name": repo.name,
                "uniques": traffic["uniques"],
                "count": traffic["count"],
                "breakdown": breakdown
            }


def get_repos_zero_traffic(repos, breakdown_dates):
    for repo in repos:
        yield {
            "name": repo.name,
            "uniques": 0,
            "count": 0,
            "breakdown": list(traffic_on_dates([], breakdown_dates))
        }


def build_summary_table(dates, repos_views, repos_clones, show_views,
                        show_clones, reverse):
    labels = [["Name", "All"] + [d.strftime("%m/%d\n%a") for d in dates]]

    data_rows = [
        [
            repo_views["name"],
            {
                "views": {
                    "uniques": repo_views["uniques"],
                    "count": repo_views["count"]
                },
                "clones": {
                    "uniques": repo_clones["uniques"],
                    "count": repo_clones["count"]
                }
            }
        ] + [
            {
                "views": {
                    "uniques": views_breakdown["uniques"],
                    "count": views_breakdown["count"]
                },
                "clones": {
                    "uniques": clones_breakdown["uniques"],
                    "count": clones_breakdown["count"]
                }
            } for views_breakdown, clones_breakdown in zip(
                repo_views["breakdown"],
                repo_clones["breakdown"]
            )
        ] for (repo_views, repo_clones) in zip(repos_views, repos_clones)
    ]

    def sort_key(r):
        return [(c["clones"]["count"], c["views"]["count"]) for c in r[2:]]

    def filter_func(r):
        return bool(r[1]["views"]["count"] + r[1]["clones"]["count"])

    def fmt_cell(c):
        if not (c["views"]["count"] + c["clones"]["count"]):
            return ""

        line_str = "{uniques}/{count}"
        lines = []

        if show_views:
            lines.append(line_str.format(**c["views"]))

        if show_clones:
            lines.append(line_str.format(**c["clones"]))

        return "\n".join(lines)

    data_rows = sorted(
        data_rows,
        key=sort_key,
        reverse=reverse
    )

    data_rows = filter(filter_func, data_rows)

    data_rows = [[r[0]] + list(map(fmt_cell, r[1:])) for r in data_rows]

    table_rows = labels + data_rows + labels
    table = AsciiTable(table_rows, "Summary")
    table.inner_row_border = True
    table.justify_columns = {
        i: "center" for i in range(1, len(dates) + 2)
    }

    return table.table
