import requests

def create_github_repo(*, git_provider_api, git_provider_url, org_name, token, repo_name, repo_description, is_private):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    data = '{"name":"' + repo_name + '","description":"' + repo_description + '","homepage":"' + git_provider_url + '","private":'+ 'true' if is_private else 'false' + ',"has_issues":true,"has_projects":true,"has_wiki":true}'

    response = requests.post(git_provider_api + '/orgs/' + org_name + '/repos', headers=headers, data=data)
    response.raise_for_status()
    
    return response

def check_github_project_exists(*, git_provider_api, org_name, token, repo_name):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    repo_name_without_git = repo_name.replace(".git", "")
    response = requests.get(f"{git_provider_api}/repos/{org_name}/{repo_name_without_git}", headers=headers)
    if response.status_code == 200:
        return True
    return False

def get_pipeline_steps(*, git_provider_api, git_provider_url, org_name, token, pipeline_name):
    # For now 'git_provider_url' it's not used
    # The idea is to get GitHub token automatically
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
    }

    print(org_name)
    response = requests.get(
        git_provider_api + '/search/repositories?q=' + pipeline_name + '+in:name+org:' + org_name,
        headers=headers,
    )
    
    response.raise_for_status()

    github_search_items = response.json()["items"]
    step_list = [{"step_repo_name": item["name"], "step_repo_git": item["html_url"]} for item in github_search_items if item["name"].startswith(f"{pipeline_name}-")]

    return step_list

def get_github_project_url(*, git_provider_api, org_name, token, repo_name):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    repo_name_without_git = repo_name.replace(".git", "")
    response = requests.get(f"{git_provider_api}/repos/{org_name}/{repo_name_without_git}", headers=headers)
    response.raise_for_status()

    return response.json()["clone_url"]
