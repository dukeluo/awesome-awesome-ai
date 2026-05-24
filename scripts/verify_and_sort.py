#!/usr/bin/env python3
import os
import re
import urllib.request
import urllib.error
import json

README_PATH = "README.md"
REPORT_PATH = "scripts/verification_report.md"

def get_github_stats(owner, repo, token=None):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Awesome-Awesome-AI-Workflow")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return {
                "stars": data.get("stargazers_count", 0),
                "last_commit": data.get("pushed_at", ""),
                "archived": data.get("archived", False),
                "exists": True,
                "error": None
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "stars": 0,
                "last_commit": "",
                "archived": False,
                "exists": False,
                "error": "404 Not Found"
            }
        elif e.code == 403 and "rate limit" in e.reason.lower():
            return {
                "stars": 0,
                "last_commit": "",
                "archived": False,
                "exists": True,
                "error": "403 Rate Limit Exceeded"
            }
        else:
            return {
                "stars": 0,
                "last_commit": "",
                "archived": False,
                "exists": True,
                "error": f"HTTP Error {e.code}"
            }
    except Exception as e:
        return {
            "stars": 0,
            "last_commit": "",
            "archived": False,
            "exists": True,
            "error": str(e)
        }

def parse_readme():
    if not os.path.exists(README_PATH):
        raise FileNotFoundError(f"{README_PATH} not found.")

    with open(README_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    parsed_sections = []
    current_section = {
        "type": "intro",
        "title": "",
        "lines": []
    }
    
    for line in lines:
        if line.startswith("## "):
            parsed_sections.append(current_section)
            title = line[3:].strip()
            current_section = {
                "type": "section",
                "title": title,
                "lines": [line]
            }
        else:
            current_section["lines"].append(line)
            
    parsed_sections.append(current_section)
    return parsed_sections

def process_table_rows(lines):
    header_lines = []
    data_rows = []
    footer_lines = []
    
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            # Check if it's header separator or column names
            if "Resource" in line or "Description" in line or re.match(r'^\|\s*[:-]+\s*\|', stripped):
                header_lines.append(line)
                in_table = True
            else:
                # It's a data row
                data_rows.append(line)
        else:
            if in_table:
                # Table ended
                footer_lines.append(line)
            else:
                header_lines.append(line)
                
    return header_lines, data_rows, footer_lines

def extract_repo_info(row):
    # Regex to find markdown link with github.com URL
    match = re.search(r'\[([^\]]+)\]\((https?://github\.com/([^/]+)/([^/\s#?)]+))', row)
    if match:
        name = match.group(1)
        url = match.group(2)
        owner = match.group(3)
        repo = match.group(4)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return name, url, owner, repo
    return None

def main():
    token = os.environ.get("GITHUB_TOKEN")
    
    print("Parsing README.md...")
    sections = parse_readme()
    
    dead_repos = []
    archived_repos = []
    errors = []
    
    updated_sections = []
    
    for section in sections:
        if section["type"] == "intro":
            updated_sections.append("".join(section["lines"]))
            continue
            
        title = section["title"]
        lines = section["lines"]
        
        if title.lower() == "contents":
            updated_sections.append("".join(lines))
            continue
            
        header_lines, data_rows, footer_lines = process_table_rows(lines)
        
        if not data_rows:
            # Keep section as is
            updated_sections.append("".join(lines))
            continue
            
        print(f"\nProcessing section: {title}")
        processed_rows = []
        
        for row in data_rows:
            info = extract_repo_info(row)
            if not info:
                # Keep non-conforming row as is
                processed_rows.append({
                    "row": row,
                    "stars": 0,
                    "last_commit": "1970-01-01T00:00:00Z",
                    "exists": True,
                    "archived": False
                })
                continue
                
            name, url, owner, repo = info
            print(f"Fetching stats for {owner}/{repo}...")
            stats = get_github_stats(owner, repo, token)
            
            if stats["error"]:
                print(f"  Error fetching stats: {stats['error']}")
                errors.append(f"- **{name}** ({url}): {stats['error']}")
                
            if not stats["exists"]:
                dead_repos.append(f"- **{name}** ({url})")
            elif stats["archived"]:
                archived_repos.append(f"- **{name}** ({url})")
                
            processed_rows.append({
                "row": row,
                "stars": stats["stars"],
                "last_commit": stats["last_commit"] if stats["last_commit"] else "1970-01-01T00:00:00Z",
                "exists": stats["exists"],
                "archived": stats["archived"]
            })
            
        # Sort rows by stars (descending), then last_commit (descending)
        processed_rows.sort(
            key=lambda x: (x["stars"], x["last_commit"]),
            reverse=True
        )
        
        # Reconstruct the section table
        new_lines = []
        new_lines.extend(header_lines)
        for item in processed_rows:
            new_lines.append(item["row"])
        new_lines.extend(footer_lines)
        
        updated_sections.append("".join(new_lines))

    # Reconstruct README.md content
    new_content = "".join(updated_sections)
    
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("\nREADME.md successfully updated and sorted!")
    
    # Write issue/report summary if issues are found
    if dead_repos or archived_repos or errors:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("# Repository Verification Report 🚨\n\n")
            f.write("The automated verification script detected issues with some listed repositories.\n\n")
            
            if dead_repos:
                f.write("## ❌ Dead Repositories (404)\n")
                f.write("These repositories are no longer available on GitHub. They should be reviewed and removed from the list.\n\n")
                f.write("\n".join(dead_repos) + "\n\n")
                
            if archived_repos:
                f.write("## ⚠️ Archived Repositories\n")
                f.write("These repositories are archived by their owners. They are read-only and may be unmaintained.\n\n")
                f.write("\n".join(archived_repos) + "\n\n")
                
            if errors:
                f.write("## ⚙️ Fetch Errors\n")
                f.write("Errors occurred while trying to query details for these repositories:\n\n")
                f.write("\n".join(errors) + "\n")
                
        print(f"Verification issues found! Report written to {REPORT_PATH}")
    else:
        if os.path.exists(REPORT_PATH):
            os.remove(REPORT_PATH)
        print("All repositories are verified, live, and sorted perfectly. No issues found.")

if __name__ == "__main__":
    main()
