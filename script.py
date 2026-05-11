import zipfile
import os

# Create folder structure
os.makedirs('output/crm-enricher/.claude/agents', exist_ok=True)

# Write files
readme_content = '''# CRM Enricher - EchoDesk Agent Workflow

Enriches 28 Oakland County realtors (Invalid Email + agent tag) using MiRealSource, Realtor.com, Zillow.

## Quick Start (No GitHub needed)
1. Unzip this folder
2. Open Claude Code in the "crm-enricher" folder  
3. Open EchoDesk with filters applied
4. Type: `Run echo-contacts-enricher`

## EchoDesk Filters
- Email status = Invalid
- Tag = agent
- Tag = oakland county (28 contacts)

## Expected Output
| Name | Office | Mailing Address | Email | DOB |
|------|--------|-----------------|-------|-----|

Copy table → Google Sheets/CRM import.'''

agent_content = '''---
name: echo-contacts-enricher
description: Enriches the currently filtered EchoDesk contact list with verified public business contact details from MiRealSource, Realtor.com, and Zillow.
tools:
  - Read
  - Search
  - WebFetch
  - Bash
permission_mode: ask
---

# EchoDesk Contact Enrichment Subagent

## Mission
Process the currently filtered EchoDesk contact list exactly as shown, then enrich each contact with verified business contact data.

## Primary workflow
1. Open the currently filtered EchoDesk contact list in EchoDesk.
2. Do not change, clear, or reapply filters unless explicitly instructed.
3. Capture every contact currently shown in the filtered list.
4. For each contact, search these sources by full name:
   - MiRealSource.com/realtors.cfm
   - Realtor.com agent search / profile pages
   - Zillow agent directory / profile pages
5. Record the best verified values for:
   - Name
   - Office
   - Mailing Address
   - Email
   - DOB
6. If an agent is not found externally, use EchoDesk data for office, email, and address when available.
7. Return one complete table for all contacts in the filtered list.

## Matching rules
- Use the filtered EchoDesk list as the source of truth for which contacts to process.
- Search by full name first, then close variants if needed.
- Prefer exact email matches when reconciling team names, office pages, or alternate listings.
- Use office, city, and mailing address as supporting evidence.
- Do not guess missing values.
- Mark unavailable fields as `not found`.

## Source priority
1. MiRealSource
2. Realtor.com
3. Zillow
4. EchoDesk fallback

## Privacy and safety
- Collect DOB only if it is explicitly visible in a permitted source and clearly tied to the agent.
- Collect mailing address only if it is explicitly shown and business-related.
- Do not infer or use private home addresses.
- Do not scrape hidden, blocked, or ambiguous personal data.
- If a source is unclear, leave the field blank or mark it `not found`.

## Output format
Return a single table in this format:

| Name | Office | Mailing Address | Email | DOB |
|------|--------|-----------------|-------|-----|
| ...  | ...    | ...             | ...   | ... |

## Quality checks
- Do not skip any contacts in the filtered EchoDesk list.
- Preserve the original EchoDesk order.
- If multiple sources disagree, choose the most directly verified match and note the ambiguity briefly after the table.
- Keep the final answer concise and structured.
'''

with open('output/crm-enricher/README.md', 'w') as f:
    f.write(readme_content)

with open('output/crm-enricher/.claude/agents/echo-contacts-enricher.md', 'w') as f:
    f.write(agent_content)

# Create ZIP
with zipfile.ZipFile('output/crm-enricher-complete.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('output/crm-enricher'):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, 'output')
            zipf.write(file_path, arcname)

print('ZIP created: output/crm-enricher-complete.zip')
print('Folder structure:')
print('crm-enricher/')
print('├── README.md')
print('└── .claude/')
print('    └── agents/')
print('        └── echo-contacts-enricher.md')