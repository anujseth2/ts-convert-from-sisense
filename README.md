# ts-convert-from-sisense

Converts a Sisense dashboard into ThoughtSpot. It reads an offline Sisense bundle
(`{dashboard, widgets, datamodel}` as JSON) and writes Table and Model TML, one Answer per
widget and a tabbed Liveboard, then lints and imports them into ThoughtSpot.

The conversion handles JAQL aggregations and the deterministic formula subset. On top of
that, this version includes:

- **Indicators become KPI tiles.** Each one has a y axis, which ThoughtSpot requires.
- **Measured values like `(count([id]), [Status])` become `group_aggregate` over a
  conditional aggregate.** The value's own filter replaces any filter on that column, the
  same way it works in Sisense.
- **Widget filters go into the Answer search,** except on a column that also has a
  dashboard filter. There, the filter is folded into each measure as a condition, because a
  Liveboard filter would otherwise replace it.
- **`metadata.ignore` is honored.** Ignoring specific dashboard filters becomes
  `query_filters ( ) - { [col] }`, and `ignore.all` becomes `{ }`.
- **Pivots with no Columns panel become flat tables,** and so do pivots with a member list
  on the Columns dimension. These are GRID_TABLE tiles in `TABLE_MODE`, with one conditional
  measure per member.
- **Hidden (disabled) widget items are dropped.**

Anything that can't be converted exactly is marked NEEDS REVIEW in `mapping.json` and in
the build output, with the reason. It is never silently downgraded.

## Derived from thoughtspot/thoughtspot-agent-skills

This repo is a standalone copy of the `ts-convert-from-sisense` skill from
[thoughtspot/thoughtspot-agent-skills](https://github.com/thoughtspot/thoughtspot-agent-skills),
along with the parts of that repo's `ts` CLI (`tools/ts-cli`) the skill needs to run. The
`.source-ref` file records the commit it was built from. The license is the original
repository's `LICENSE`.

Only these `ts` command groups are included: `sisense`, `tml`, `auth` and `profiles`.

## Layout

```
agents/cli/ts-convert-from-sisense/   the skill (SKILL.md + references)
agents/cli/ts-profile-thoughtspot/    ThoughtSpot profile and credential setup the skill links to
agents/shared/                        reference docs the skill reads (formula mapping, TML schemas)
ts_cli/                               the trimmed `ts` CLI
tests/                                the skill's unit tests
examples/retail_orders.bundle.json    a synthetic sample bundle
```

Some links in the shared schema docs point to sibling docs that aren't copied here. Those
docs are background reading that the skill doesn't need.

## Install

You need Python 3.10 or later.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

That puts `ts` on your PATH. To use the skill from Claude Code, link the skill folders and
the shared docs into place. The skill's links are relative (`../../shared/...`), so it
resolves them from `~/.claude/skills`:

```bash
ln -s "$PWD/agents/cli/ts-convert-from-sisense" ~/.claude/skills/ts-convert-from-sisense
ln -s "$PWD/agents/cli/ts-profile-thoughtspot" ~/.claude/skills/ts-profile-thoughtspot
ln -s "$PWD/agents/shared" ~/.claude/shared
```

Then set up a ThoughtSpot profile with `/ts-profile-thoughtspot` or `ts profiles add`.
Credentials stay in the OS keychain and are never written to a file.

## Run

Here is the offline part, run on the sample bundle:

```bash
mkdir -p out
ts sisense parse -i examples/retail_orders.bundle.json -o out/inventory.json
ts sisense build-model -i examples/retail_orders.bundle.json \
    -c "My Connection" --database DEMO --schema PUBLIC -o out
ts sisense build-liveboard -i examples/retail_orders.bundle.json \
    --model-name "Retail Orders" -o out
ts tml lint --dir out
```

To import into ThoughtSpot (this needs a profile, and the tables must exist in the
connection):

```bash
ts tml import --dir out/ --pattern '*.tml' --order tableau --policy ALL_OR_NONE --profile <name>
ts tml verify-render <liveboard-guid> --profile <name>
```

`agents/cli/ts-convert-from-sisense/SKILL.md` has the full procedure: review gates,
overrides, and binding the Liveboard to an existing Model.

## Tests

```bash
pytest
```
