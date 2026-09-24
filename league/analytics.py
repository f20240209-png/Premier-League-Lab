from collections import defaultdict
from .importer import FINISHED


def result_for(match, team_id):
    gf, ga = (match.home_score, match.away_score) if match.home_id == team_id else (match.away_score, match.home_score)
    return {"gf": gf, "ga": ga, "points": 3 if gf > ga else 1 if gf == ga else 0,
            "result": "W" if gf > ga else "D" if gf == ga else "L"}


def standings(matches, teams, overrides=None):
    """Computed from results; no separate totals can drift after an import."""
    rows = {}
    overrides = overrides or {}
    for match in matches:
        for tid in (match.home_id, match.away_id):
            if tid not in rows:
                rows[tid] = dict(id=tid, name=teams[tid].name, logo=teams[tid].logo,
                                played=0, won=0, drawn=0, lost=0, gf=0, ga=0, gd=0, points=0, form=[])
        if match.status not in FINISHED and match.id not in overrides:
            continue
        home_score, away_score = overrides.get(match.id, (match.home_score, match.away_score))
        if home_score is None or away_score is None:
            continue
        for tid, gf, ga in ((match.home_id, home_score, away_score), (match.away_id, away_score, home_score)):
            row = rows[tid]
            row["played"] += 1
            row["gf"] += gf
            row["ga"] += ga
            row["gd"] = row["gf"] - row["ga"]
            outcome = "W" if gf > ga else "D" if gf == ga else "L"
            row[{"W": "won", "D": "drawn", "L": "lost"}[outcome]] += 1
            row["points"] += {"W": 3, "D": 1, "L": 0}[outcome]
            row["form"] = (row["form"] + [outcome])[-5:]
    # Alphabetical order is only a display fallback, not an official tiebreak.
    return sorted(rows.values(), key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["name"]))


def team_analysis(matches, team_id):
    finished = [m for m in matches if m.status in FINISHED and team_id in (m.home_id, m.away_id)]
    splits = {}
    for label, selected in (("Overall", finished), ("Home", [m for m in finished if m.home_id == team_id]),
                            ("Away", [m for m in finished if m.away_id == team_id])):
        results = [result_for(m, team_id) for m in selected]
        n = len(results)
        splits[label] = {"played": n, "ppg": round(sum(r["points"] for r in results) / n, 2) if n else None,
                         "gf_pg": round(sum(r["gf"] for r in results) / n, 2) if n else None,
                         "ga_pg": round(sum(r["ga"] for r in results) / n, 2) if n else None,
                         "clean_sheets": sum(r["ga"] == 0 for r in results)}
    points, history = 0, []
    for i, m in enumerate(finished):
        points += result_for(m, team_id)["points"]
        history.append({"game": i + 1, "date": m.kickoff.strftime("%d %b"), "points": points})
    return {"splits": splits, "history": history, "recent": finished[-5:][::-1],
            "form": [result_for(m, team_id)["result"] for m in finished[-5:]]}


def history_features(history, home_id, away_id):
    """Only previously completed matches. Minimum three per club."""
    if len(history[home_id]) < 3 or len(history[away_id]) < 3:
        return None
    features = []
    for tid in (home_id, away_id):
        recent = history[tid][-5:]
        features.extend(sum(r[field] for r in recent) / len(recent) for field in ("points", "gf", "ga"))
    return features


FEATURES = ["Home recent points/game", "Home recent goals/game", "Home recent conceded/game",
            "Away recent points/game", "Away recent goals/game", "Away recent conceded/game"]


def feature_rows(matches):
    """Use results from earlier UTC dates, excluding overlapping same-day games."""
    from itertools import groupby
    history, rows = defaultdict(list), []
    for _, group in groupby(sorted(matches, key=lambda m: m.kickoff), key=lambda m: m.kickoff.date()):
        batch = list(group)
        for m in batch:
            x = history_features(history, m.home_id, m.away_id)
            if m.status in FINISHED and x is not None:
                y = "H" if m.home_score > m.away_score else "D" if m.home_score == m.away_score else "A"
                rows.append({"match": m, "x": x, "y": y})
        for m in batch:
            if m.status in FINISHED:
                history[m.home_id].append(result_for(m, m.home_id))
                history[m.away_id].append(result_for(m, m.away_id))
    return rows
