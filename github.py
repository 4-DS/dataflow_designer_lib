import requests

def create_github_repo(*, org_name, token, repo_name, repo_description, is_private):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    data = '{"name":"' + repo_name + '","description":"' + repo_description + '","homepage":"https://github.com","private":'+ 'true' if is_private else 'false' + ',"has_issues":true,"has_projects":true,"has_wiki":true}'

    response = requests.post('https://api.github.com/orgs/' + org_name + '/repos', headers=headers, data=data)
    
    return response

def get_pipeline_steps(*, org_name, token, pipeline_name):
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
    }
    
    response = requests.get(
        'https://api.github.com/search/repositories?q=' + pipeline_name + '+in:name+org:' + org_name,
        headers=headers,
    )
    
    response.raise_for_status()

    github_search_items = response.json()["items"]
    step_list = [{"step_repo_name": item["name"], "step_repo_git": item["html_url"]} for item in github_search_items if item["name"].startswith(f"{pipeline_name}-")]

    return step_list
