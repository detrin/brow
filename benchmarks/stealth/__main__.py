import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from benchmarks.stealth import runners, signals, sites

DEFAULT_RUNNERS = ["brow", "patchright", "patchright-bare", "agent-browser"]


async def measure(name, tmp_root, with_sites):
    entry = {"runner": name, "available": True}
    try:
        runner = runners.build(name, tmp_root)
    except KeyError:
        return {"runner": name, "available": False, "reason": "unknown runner"}

    try:
        await runner.start()
    except runners.Unavailable as e:
        return {"runner": name, "available": False, "reason": str(e)}
    except Exception as e:
        return {"runner": name, "available": False, "reason": f"{type(e).__name__}: {e}"}

    try:
        await runner.goto("https://example.com")
        probe = await runner.probe()
        entry["probe"] = probe
        unusable = signals.unusable(probe)
        if unusable:
            entry["error"] = f"fingerprint not measured: {unusable}"
        else:
            entry["fingerprint"] = signals.score(probe)

        if with_sites:
            entry["sites"] = {}
            for site in sites.SITES:
                started = time.monotonic()
                try:
                    status = await runner.goto(site["url"])
                    text = await runner.text_sample()
                    verdict, why = sites.classify(status, text, site["expect"])
                except Exception as e:
                    verdict, why = "error", f"{type(e).__name__}: {e}"
                entry["sites"][site["id"]] = {
                    "verdict": verdict,
                    "why": why,
                    "seconds": round(time.monotonic() - started, 1),
                }
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
    finally:
        try:
            await runner.stop()
        except Exception:
            pass
    return entry


VERDICT_MARK = {"through": "through", "blocked": "BLOCKED", "error": "error"}


def report(results, host):
    live = [r for r in results if r.get("fingerprint")]
    lines = [
        "# Stealth benchmark",
        "",
        f"Host: {host['system']} / `navigator.platform` should be `{host['platform']}` / timezone `{host['timezone']}`",
        "",
        "## Fingerprint checks",
        "",
        "Deterministic: pure JS on a control page, no third-party detector involved.",
        "",
    ]

    if not live:
        lines += ["No runner produced a fingerprint.", ""]
    else:
        names = [r["runner"] for r in live]
        lines.append("| Check | " + " | ".join(names) + " |")
        lines.append("|---|" + "|".join(["---"] * len(names)) + "|")
        for check, _test, _why in signals.CHECKS:
            row = []
            for r in live:
                c = r["fingerprint"]["checks"].get(check)
                row.append("pass" if c and c["pass"] else "**FAIL**")
            lines.append(f"| {check} | " + " | ".join(row) + " |")
        lines.append(
            "| **score** | " + " | ".join(f"**{r['fingerprint']['passed']}/{r['fingerprint']['total']}**" for r in live) + " |"
        )
        lines.append("")

    with_sites = [r for r in results if r.get("sites")]
    if with_sites:
        lines += ["## Real sites", "", "Live third-party sites. Informational, not a gate — these verdicts move on someone else's schedule.", ""]
        names = [r["runner"] for r in with_sites]
        lines.append("| Site | " + " | ".join(names) + " |")
        lines.append("|---|" + "|".join(["---"] * len(names)) + "|")
        for site in sites.SITES:
            row = []
            for r in with_sites:
                s = r["sites"].get(site["id"])
                row.append(VERDICT_MARK.get(s["verdict"], "?") if s else "-")
            lines.append(f"| `{site['id']}` | " + " | ".join(row) + " |")
        lines.append("")
        for site in sites.SITES:
            lines.append(f"- `{site['id']}` — {site['note']}")
        lines.append("")

    skipped = [r for r in results if not r.get("available")]
    if skipped:
        lines += ["## Not measured", ""]
        lines += [f"- **{r['runner']}** — {r['reason']}" for r in skipped]
        lines.append("")

    failed = [r for r in results if r.get("error")]
    if failed:
        lines += ["## Errors", ""]
        lines += [f"- **{r['runner']}** — {r['error']}" for r in failed]
        lines.append("")

    lines += [
        "## Reading this",
        "",
        "A failing check is a signal a detector can read for free; it is not proof of a block, and passing every",
        "check is not proof of access. The fingerprint table is the regression test — run it after every",
        "`patchright` bump. The site table is the outcome, and it is noisy by nature.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Measure how automated each browser runner looks")
    p.add_argument("--runners", default=",".join(DEFAULT_RUNNERS), help=f"comma-separated; known: {','.join(runners.REGISTRY)}")
    p.add_argument("--sites", action="store_true", help="Also visit live third-party sites (slow, noisy)")
    p.add_argument("--output", default="benchmarks/stealth/results")
    args = p.parse_args()

    names = [n.strip() for n in args.runners.split(",") if n.strip()]
    host = signals.host_context()

    async def go():
        with tempfile.TemporaryDirectory(prefix="stealth-bench-") as tmp:
            return [await measure(n, tmp, args.sites) for n in names]

    results = asyncio.run(go())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"host": host, "sites_included": args.sites, "results": results}
    (out / "results.json").write_text(json.dumps(payload, indent=2, default=str))
    text = report(results, host)
    (out / "report.md").write_text(text)
    print(text)
    print(f"Wrote {out / 'report.md'} and {out / 'results.json'}")


if __name__ == "__main__":
    main()
