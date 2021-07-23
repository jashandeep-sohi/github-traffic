import datetime
import logging
import click
import json

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
@click.pass_context
def cli(ctx, token, user, password, ignore, include, output_format, order):
    ctx.ensure_object(dict)

    ctx.obj["output_format"] = output_format
    ctx.obj["order"] = order

    if token:
        github = Github(token)
    else:
        github = Github(user, password)

    repos = github.get_user().get_repos()

    ignore_repo_names = {x.strip() for x in ignore.split(",") if x.strip()}
    include_repo_names = {x.strip() for x in include.split(",") if x.strip()}

    ctx.obj["github"] = github
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

    metrics = set(metrics)

    show_views = "views" in metrics
    show_clones = "clones" in metrics

    today = datetime.datetime.utcnow().date()

    dates = list(reversed(list(
        date_days_range(today - datetime.timedelta(days=days-1), today)
    )))

    fake_traffic = list(get_repos_zero_traffic(repos, dates))

    if show_views:
        p = progressbar(
            repos,
            show_eta=False,
            label="Fetching views stats",
            item_show_func=lambda r: r and r.name
        )
        with p:
            repos_views = list(get_repos_views_traffic(p, dates))
    else:
        repos_views = fake_traffic

    if show_clones:
        p = progressbar(
            repos,
            show_eta=False,
            label="Fetching clones stats",
            item_show_func=lambda r: r and r.name
        )
        with p:
            repos_clones = list(get_repos_clones_traffic(p, dates))
    else:
        repos_clones = fake_traffic

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

    prog = progressbar(
        repos,
        show_eta=False,
        label="Fetching referrers stats",
        item_show_func=lambda r: r and r.name
    )
    with prog:
        referrers = [
            {
                "repo": repo.name,
                "referrer": r.referrer,
                "count": r.count,
                "uniques": r.uniques
            } for repo in prog for r in repo.get_top_referrers()

        ]
    referrers = sorted(
      referrers,
      key=lambda x: (x["uniques"], x["count"]),
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

    prog = progressbar(
        repos,
        show_eta=False,
        label="Fetching paths stats",
        item_show_func=lambda r: r and r.name
    )
    with prog:
        paths = [
            {
                "repo": repo.name,
                "path": p.path,
                "title": p.title,
                "count": p.count,
                "uniques": p.uniques
            } for repo in prog for p in repo.get_top_paths()

        ]
    paths = sorted(
      paths,
      key=lambda x: (x["uniques"], x["count"]),
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


def get_repos_views_traffic(repos, breakdown_dates):
    for repo in repos:
        traffic = repo.get_views_traffic()
        breakdown = list(traffic_on_dates(traffic["views"], breakdown_dates))
        yield {
            "name": repo.name,
            "uniques": traffic["uniques"],
            "count": traffic["count"],
            "breakdown": breakdown
        }


def get_repos_clones_traffic(repos, breakdown_dates):
    for repo in repos:
        traffic = repo.get_clones_traffic()
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
