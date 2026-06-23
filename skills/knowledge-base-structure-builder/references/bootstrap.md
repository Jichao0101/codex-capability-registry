# Bootstrap Mode

Use Bootstrap mode when the target directory is empty, nearly empty, or lacks the basic knowledge-base zones.

## Create Standard Zones

Create:

- `01_Knowledge/`
- `02_Projects/`
- `03_Inbox/`
- `04_Sources/`
- `90_Archive/`

Optional project-internal audit area:

- `02_Projects/Knowledge-Base/`

## Create Entry Files

Create these files with conservative language:

- `README.md`
- `01_Knowledge/知识总览.md` or `01_Knowledge/Knowledge Overview.md`
- `02_Projects/项目总览.md` or `02_Projects/Projects Overview.md`
- `03_Inbox/候选内容索引.md` or `03_Inbox/Candidate Index.md`
- `04_Sources/来源索引.md` or `04_Sources/Source Index.md`
- `02_Projects/Knowledge-Base/知识库结构审计_current.md` or equivalent

Use `assets/*.template.md` when useful.

After copying templates:

- replace `YYYY-MM-DD` with the actual update date
- localize entry filenames when the target knowledge base uses a non-English convention
- remove or explicitly track leftover `TBD` placeholders
- verify `README.md` links match the actual overview filenames

## Initial Status

Use conservative statuses:

- empty entries: `active`
- structure audit: `active`
- initial knowledge items: do not mark `verified` unless already reviewed

Do not create current document groups during Bootstrap unless the user has a concrete project module with enough source material.
