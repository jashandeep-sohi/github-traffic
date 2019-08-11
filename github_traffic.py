import datetime
import logging
import click
import json

from github import Github
from terminaltables import AsciiTable


logger = logging.getLogger(__name__)


@click.group()
@click.option("--token", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.pass_context
def cli(ctx, token, user, password):
    ctx.ensure_object(dict)

    if token:
        github = Github(token)
    else:
        github = Github(user, password)

    repos = github.get_user().get_repos()

    ctx.obj["github"] = github
    ctx.obj["repos"] = list(filter_traffic_visible(repos))


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


def build_traffic_table(views, clones, dates, table_days_visible, metrics):
    dates_visible = dates[:table_days_visible]

    def f(x):
        return [
            (b["count"], a["count"])
            for (a, b) in zip(x[0]["breakdown"], x[1]["breakdown"])
        ]

    sorted_views_clones = sorted(
        zip(views, clones),
        key=f
    )

    rows = []
    for view, clone in sorted_views_clones:
        if view["count"] == 0 and clone["count"] == 0:
            continue

        all_col_lines = []

        line_str = "{uniques}/{count}"

        if "views" in metrics:
            all_col_lines.append(line_str.format(**view))

        if "clones" in metrics:
            all_col_lines.append(line_str.format(**clone))

        all_col = "\n".join(all_col_lines)

        breakdown_cols = []
        view_clone_breakdown = zip(
            view["breakdown"],
            clone["breakdown"],
            dates_visible
        )
        for view_breakdown, clone_breakdown, _ in view_clone_breakdown:
            if view_breakdown["count"] + clone_breakdown["count"] > 0:
                breadown_col_lines = []

                if "views" in metrics:
                    breadown_col_lines.append(
                        line_str.format(**view_breakdown)
                    )

                if "clones" in metrics:
                    breadown_col_lines.append(
                        line_str.format(**clone_breakdown)
                    )

                breakdown_cols.append("\n".join(breadown_col_lines))
            else:
                breakdown_cols.append("")

        rows.append([view["name"], all_col] + breakdown_cols)

    labels = [["Name", "All"] + [
        d.strftime("%m/%d\n%a") for d in dates_visible]
    ]
    table_data = labels + rows + labels
    table = AsciiTable(table_data)
    table.inner_row_border = True
    table.justify_columns = {
        i: "center" for i in range(1, len(dates_visible) + 2)
    }

    return table.table


@cli.command()
@click.option(
    "--metrics",
    default=["views", "clones"],
    type=click.Choice(["views", "clones"]),
    multiple=True
)
@click.option(
    "--output-format",
    default="table",
    type=click.Choice(["table", "json"])
)
@click.option("--table-days-visible", default=15, type=click.IntRange(1, 15))
@click.pass_context
def breakdown(ctx, metrics, output_format, table_days_visible):
    repos = ctx.obj.get("repos")
    metrics = set(metrics)

    today = datetime.datetime.utcnow().date()

    dates = list(reversed(list(
        date_days_range(today - datetime.timedelta(days=14), today)
    )))

    if "views" in metrics:
        views = list(get_repos_views_traffic(repos, dates))
    else:
        views = list(get_repos_zero_traffic(repos, dates))

    if "clones" in metrics:
        clones = list(get_repos_clones_traffic(repos, dates))
    else:
        clones = list(get_repos_zero_traffic(repos, dates))

    if output_format == "json":
        out = {
            "views": views if "views" in metrics else None,
            "clones": clones if "clones" in metrics else None
        }
        click.echo(json.dumps(out, default=str, indent=4, sort_keys=True))
    elif output_format == "table":
        table = build_traffic_table(
            views, clones, dates, table_days_visible, metrics
        )
        click.secho(table)


@cli.command()
@click.option(
    "--output-format",
    default="table",
    type=click.Choice(["table", "json"])
)
@click.pass_context
def referrers(ctx, output_format):
    repos = ctx.obj.get("repos")

    referrers = [
        {
            "repo": repo.name,
            "referrer": r.referrer,
            "count": r.count,
            "uniques": r.uniques
        } for repo in repos for r in repo.get_top_referrers()

    ]
    referrers = sorted(referrers, key=lambda x: (x["uniques"], x["count"]))

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
@click.option(
    "--output-format",
    default="table",
    type=click.Choice(["table", "json"])
)
@click.pass_context
def paths(ctx, output_format):
    repos = ctx.obj.get("repos")

    paths = [
        {
            "repo": repo.name,
            "path": p.path,
            "title": p.title,
            "count": p.count,
            "uniques": p.uniques
        } for repo in repos for p in repo.get_top_paths()

    ]
    paths = sorted(paths, key=lambda x: (x["uniques"], x["count"]))

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
